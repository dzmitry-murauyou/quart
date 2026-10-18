#!/usr/bin/env python3
"""Strict audit of the ENHANCED schematic (RD1/RD2 strobes + validity gating +
buffer enabletr recirculation) against the UNCHANGED committed Block1.vwf.

Semantics modelled (matches Quartus functional netlist behaviour):
  RD1/RD2 : 1-bit DFFs on raw clk, RD1<=Read, RD2<=RD1;
  eq0/eq1 : decode outputs = Read & !ROM_RAM / Read & ROM_RAM;
  rom_valid = eq0 & RD2  -> bustri4.enabledt (ROM q onto ShD);
  ram_valid = eq1 & RD1  -> bustri5.enabledt (RAM q onto ShD);
  buffer read pin = (rom_valid | ram_valid) & Read (inst13+inst14);
  buffer write pin = clk & Write (unchanged);
  buffer chain clocks on spine = clk & (read_pin | write_pin);
  bustri0.enabletr = read_pin | write_pin  (recirculation, no X);
  chain DFF samples ShD with setup: value just before the edge, except during
  write windows where bustri0 settles to r5 right after clk rise.
"""
import sys
sys.path.insert(0, 'tools')
from sim_check import mif_load, parse_vwf_inputs, value_at, b2h, Z, clean_for_reg

DUR = 860.0


def simulate2(sigs, dur, rom_mem, ram_mem):
    times = set()
    for tl in sigs.values():
        for (t0, _) in tl:
            times.add(round(t0, 6))
    times = sorted(t for t in times if t <= dur + 1e-9)

    rom_addr_reg, rom_out_reg, ram_addr_reg = 0, '0' * 8, 0
    ram = dict(ram_mem)
    chain = ['0' * 8] * 6
    RD1 = RD2 = 0
    prev_clk = prev_g_rom = prev_g_ram = 0
    events, bus_trace = [], []

    def A_at(t):
        return int(''.join(value_at(sigs['Address[%d]' % b], t)
                           for b in [5, 4, 3, 2, 1, 0]), 2)

    def bus_level(eq0, eq1, rd2, rd1, clk, write, rom_q, ram_q, r5):
        if eq0 and rd2:
            return rom_q
        if eq1 and rd1:
            return ram_q
        if clk and write:
            return r5
        return Z * 8

    for t in times:
        clk = int(value_at(sigs['clk'], t))
        read = int(value_at(sigs['Read'], t))
        write = int(value_at(sigs['Write'], t))
        rrsel = int(value_at(sigs['ROM_RAM'], t))
        A = A_at(t)
        rising = clk == 1 and prev_clk == 0

        eq0 = read & (1 - rrsel)
        eq1 = read & rrsel
        rom_q_pre, ram_q_pre = rom_out_reg, ram.get(ram_addr_reg, 'X' * 8)

        g_rom = clk & read
        g_ram = clk & (read | write)

        # pre-edge validity (strobe state before this edge)
        rv_pre = eq0 & RD2
        rv2_pre = eq1 & RD1
        read_pin_pre = (rv_pre | rv2_pre) & read
        chain_edge = rising and (read_pin_pre == 1 or write == 1)

        # memory edges
        if g_rom and not prev_g_rom:
            rom_out_reg = rom_mem.get(rom_addr_reg, 'X' * 8)
            rom_addr_reg = A
        if g_ram and not prev_g_ram:
            if write:
                ram[A] = clean_for_reg(chain[5])
                events.append((t, 'ram_wr', A, chain[5]))
            ram_addr_reg = A

        # buffer chain sample
        if chain_edge:
            if write:
                sample = clean_for_reg(chain[5])
            elif rv_pre:
                sample = clean_for_reg(rom_q_pre)
            elif rv2_pre:
                sample = clean_for_reg(ram_q_pre)
            else:
                sample = Z * 8
            chain = [sample] + chain[:5]
            events.append((t, 'buf_latch', sample))

        # strobes on raw clk rise
        if rising:
            RD2, RD1 = RD1, read

        # observable bus level after all updates at t
        bus = bus_level(eq0, eq1, RD2, RD1, clk, write,
                        rom_out_reg, ram.get(ram_addr_reg, 'X' * 8), chain[5])
        bus_trace.append((t, clk, bus))
        prev_clk = clk
        prev_g_rom, prev_g_ram = g_rom, g_ram
    return ram, chain, events, bus_trace


def main():
    rom = mif_load('lab3/rom.mif')
    ram0 = mif_load('lab3/ram.mif')
    sigs, dur = parse_vwf_inputs('lab3/Block1.vwf')
    ram, chain, events, bus_trace = simulate2(sigs, dur, rom, ram0)
    ok = True

    def chk(label, cond):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label)
        ok = ok and cond

    print('--- RAM final dump ---')
    for a in [0x00] + list(range(0x0A, 0x10)) + list(range(0x30, 0x3E)):
        print('  [%02X]=%s' % (a, b2h(ram.get(a, '??'))), end='')
    print()
    chk('mem[0x30..0x35] == 11..66',
        [b2h(ram[a]) for a in range(0x30, 0x36)] == ['11', '22', '33', '44', '55', '66'])
    chk('mem[0x38..0x3D] == AA..FF',
        [b2h(ram[a]) for a in range(0x38, 0x3E)] == ['AA', 'BB', 'CC', 'DD', 'EE', 'FF'])
    chk('mem[0x0A..0x0F] intact',
        [b2h(ram[a]) for a in range(0x0A, 0x10)] == ['AA', 'BB', 'CC', 'DD', 'EE', 'FF'])
    chk('mem[0] == FF', b2h(ram[0]) == 'FF')

    needed = {'11', '22', '33', '44', '55', '66',
              'AA', 'BB', 'CC', 'DD', 'EE', 'FF'}
    rl = [e for e in events if e[1] == 'buf_latch' and not (260 <= e[0] < 380 or 620 <= e[0] < 740)]
    wl = [e for e in events if e[1] == 'buf_latch' and (260 <= e[0] < 380 or 620 <= e[0] < 740)]
    print('--- buffer latch samples (read phases) ---')
    print('  ', [b2h(e[2]) for e in rl])
    print('--- recirculation samples (write phases, benign) ---')
    print('  ', [b2h(e[2]) for e in wl])
    chk('exactly 12 read-phase latch edges (6+6)', len(rl) == 12)
    chk('latched bytes = exactly the 12 needed, in order',
        [b2h(e[2]) for e in rl] == ['11', '22', '33', '44', '55', '66',
                                    'AA', 'BB', 'CC', 'DD', 'EE', 'FF'])
    chk('write phases only recirculate own bytes (no X/Z)',
        all(b2h(e[2]) in needed for e in wl))
    chk('final chain r5..r0 == AA..FF',
        [b2h(c) for c in chain[::-1]] == ['AA', 'BB', 'CC', 'DD', 'EE', 'FF'])

    print('--- ShD bus level trace (non-Z segments) ---')
    segs, cur = [], None
    for (t, clk, bus) in bus_trace + [(DUR, 0, Z * 8)]:
        h = 'Z' if bus == Z * 8 else b2h(bus)
        if cur is None or cur[2] != h:
            if cur: segs.append((cur[0], t, cur[2]))
            cur = (t, t, h)
        else:
            cur = (cur[0], t, h)
    for s in segs:
        if s[2] != 'Z':
            print('   [%6.1f, %6.1f) = %s' % s)
    bad = [s for s in segs if s[2] not in needed and s[2] != 'Z']
    chk('bus carries ONLY needed bytes (no X/junk/00)', not bad)
    def bus_at(tq):
        v = Z * 8
        for (t, clk, bus) in bus_trace:
            if t <= tq:
                v = bus
            else:
                break
        return 'Z' if v == Z * 8 else b2h(v)
    chk('bus Z in idle gaps',
        [bus_at(t) for t in (50, 240, 400, 600, 800)] == ['Z'] * 5)
    win = [(90, 220), (260, 380), (450, 580), (620, 740)]
    chk('bus driven only inside activity windows',
        all(any(a <= s[0] and s[1] <= b for (a, b) in win)
            for s in segs if s[2] != 'Z'))
    wr = [e for e in events if e[1] == 'ram_wr']
    print('--- RAM writes ---')
    for e in wr:
        print('   t=%g addr=%02X data=%s' % (e[0], e[2], b2h(e[3])))
    chk('12 RAM writes, correct addr/data order',
        [(e[2], b2h(e[3])) for e in wr] ==
        list(zip(range(0x30, 0x36), ['11', '22', '33', '44', '55', '66'])) +
        list(zip(range(0x38, 0x3E), ['AA', 'BB', 'CC', 'DD', 'EE', 'FF'])))
    print('\nALL PASS' if ok else '\nFAILURES PRESENT')
    return 0 if ok else 1


sys.exit(main())
