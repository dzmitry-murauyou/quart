#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cycle-accurate checker for the Block1 (SIFO lab 3, var 12) design.

Models exactly what Quartus II 9.1 functional simulation does:
  * lpm_rom0  : altsyncram ROM, address registered by inclock, output
                registered by outclock (CLOCK1)        -> 2-cycle latency
  * lpm_ram_dq0: altsyncram SINGLE_PORT, address+write registered by
                 inclock, output UNREGISTERED           -> 1-cycle latency,
                 read-during-write returns NEW data
  * buffer_6byte: 6 x lpm_dff shift chain (r0..r5), clock = clk & (read|write)
                latching Z/X produces X
  * lpm_bustri0 (buffer): result = enabletr(read) ? bus : Z ;
                          bus <- r5 when enabledt(write)
  * lpm_bustri1 x2:  bus <- ROM_q when eq0 (Read & ~ROM_RAM)
                     bus <- RAM_q when eq1 (Read &  ROM_RAM)
  * gated clocks are plain AND levels -> a rising level change of
    clk&(read|write) at ANY moment (even mid clk-high) clocks RAM+buffer
    (this is the glitch mechanism).
Zero-delay / non-blocking semantics: at each timepoint first settle inputs
and combinational bus, then apply all clocked updates with pre-edge state.
"""
import re, sys

X, Z = 'X', 'Z'

def mif_load(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    mem = {}
    body = txt.split('CONTENT BEGIN')[1].split('END;')[0]
    for line in body.splitlines():
        line = line.strip().rstrip(';').strip()
        if not line or line.startswith('--'):
            continue
        m = re.match(r'\[([0-9A-Fa-f]+)\.\.([0-9A-Fa-f]+)\]\s*:\s*([0-9A-Fa-f]+)', line)
        if m:
            a0, a1, v = int(m.group(1), 16), int(m.group(2), 16), h2b(m.group(3))
            for a in range(a0, a1 + 1):
                mem[a] = v
            continue
        m = re.match(r'([0-9A-Fa-f]+)\s*:\s*([0-9A-Fa-f]+)', line)
        if m:
            mem[int(m.group(1), 16)] = h2b(m.group(2))
    return mem

def h2b(h):          # hex byte -> 8-char bit string
    return format(int(h, 16), '08b')

def b2h(b):          # 8-char bit string -> hex-ish display
    if all(c in '01' for c in b):
        return format(int(b, 2), '02X')
    return ''.join(c if c in '01' else c for c in b)

def hx(v):           # 8-bit clean value -> 2-char hex string
    return v

def parse_vwf_inputs(path):
    """returns dict sig -> list[(t_start, level)] and duration"""
    txt = open(path, encoding='utf-8', errors='replace').read()
    dur = float(re.search(r'DATA_DURATION = ([\d.]+)', txt).group(1))
    sigs = {}
    for sig in ['clk', 'Read', 'ROM_RAM', 'Write',
                'Address[5]', 'Address[4]', 'Address[3]',
                'Address[2]', 'Address[1]', 'Address[0]']:
        m = re.search(r'TRANSITION_LIST\("' + re.escape(sig) + r'"\)\s*\{(.*?)\n\}\n', txt, re.S)
        body = m.group(1)
        toks = re.findall(r'REPEAT = (\d+);|LEVEL (\S+) FOR ([\d.]+);|NODE|\{|\}', body)
        # recursive expansion
        out = []
        def expand(items, rep):
            for it in items:
                if it[0] == 'L':
                    for _ in range(rep):
                        out.append((it[1], float(it[2])))
                else:
                    expand(it[1], it[2] * rep if it[2] else rep)
        # build tree
        pos = 0
        raw = body
        # simpler: token stream parse
        i = 0
        tokens = []
        for m2 in re.finditer(r'NODE|\{|REPEAT = (\d+);|LEVEL (\S+) FOR ([\d.]+);|\}', raw):
            t = m2.group(0)
            if t == 'NODE': tokens.append(('NODE',))
            elif t == '{': tokens.append(('{',))
            elif t == '}': tokens.append(('}',))
            elif t.startswith('REPEAT'): tokens.append(('R', int(m2.group(1))))
            else: tokens.append(('L', m2.group(2), float(m2.group(3))))
        def parse(i):
            items = []
            while i < len(tokens) and tokens[i][0] != '}':
                tk = tokens[i]
                if tk[0] == 'NODE':
                    i += 1
                    assert tokens[i][0] == '{'; i += 1
                    rep = 1
                    if tokens[i][0] == 'R':
                        rep = tokens[i][1]; i += 1
                    sub, i = parse(i)
                    assert tokens[i][0] == '}'; i += 1
                    items.append(('N', sub, rep))
                elif tk[0] == '{':
                    i += 1
                    sub, i = parse(i)
                    assert tokens[i][0] == '}'; i += 1
                    items.append(('N', sub, 1))
                else:
                    items.append(('L', tk[1], tk[2])); i += 1
            return items, i
        items, _ = parse(0)
        flat = []
        def fl(items):
            for it in items:
                if it[0] == 'L':
                    flat.append((it[1], it[2]))
                else:
                    for _ in range(it[2]):
                        fl(it[1])
        fl(items)
        # to absolute timeline
        tl = []
        t = 0.0
        for lvl, d in flat:
            tl.append((t, lvl))
            t += d
        assert abs(t - dur) < 1e-6, (sig, t, dur)
        sigs[sig] = tl
    return sigs, dur

def value_at(tl, t):
    v = '0'
    for (t0, lvl) in tl:
        if t0 <= t + 1e-9:
            v = lvl
        else:
            break
    return v

def bus_byte(bits):
    return ''.join(bits)

def resolve(drivers):
    """drivers: list of 8-char strings (may contain Z). Return resolved 8-char."""
    if not drivers:
        return Z * 8
    res = []
    for b in range(8):
        vals = set(d[b] for d in drivers)
        vals.discard(Z)
        if not vals:
            res.append(Z)
        elif len(vals) == 1:
            res.append(vals.pop())
        else:
            res.append(X)
    return ''.join(res)

def clean_for_reg(v):
    """DFF/memory latch of Z or X bits -> X"""
    return ''.join(c if c in '01' else X for c in v)

def simulate(sigs, dur, rom_mem, ram_mem, verbose_until=0.0):
    # collect event times
    times = set()
    for tl in sigs.values():
        for (t0, _) in tl:
            times.add(round(t0, 6))
    times = sorted(t for t in times if t <= dur + 1e-9)

    # state
    rom_addr_reg = 0
    rom_out_reg = '0' * 8
    ram_addr_reg = 0
    ram = dict(ram_mem)
    chain = ['0' * 8] * 6          # r0..r5 (r0 = inst10 input stage, r5 = inst13 tail)

    prev_g_rom = 0
    prev_g_ram = 0
    log = []
    bus_trace = []              # (t, busvalue)

    def A_at(t):
        return int(''.join(value_at(sigs['Address[%d]' % b], t) for b in [5, 4, 3, 2, 1, 0]), 2)

    last_bus = Z * 8
    for t in times:
        clk = int(value_at(sigs['clk'], t))
        read = int(value_at(sigs['Read'], t))
        write = int(value_at(sigs['Write'], t))
        rrsel = int(value_at(sigs['ROM_RAM'], t))
        A = A_at(t)

        g_rom = clk & read
        g_ram = clk & (read | write)

        # combinational bus (with pre-edge register state)
        drivers = []
        eq0 = read & (1 - rrsel)
        eq1 = read & rrsel
        ram_q = ram.get(ram_addr_reg, 'X'*8)
        rom_q = rom_out_reg
        if eq0: drivers.append(rom_q)
        if eq1: drivers.append(ram_q)
        if write: drivers.append(chain[5])
        bus = resolve(drivers)
        result = bus if read else (Z * 8)

        if t < verbose_until:
            log.append((t, clk, read, write, rrsel, A, g_rom, g_ram, bus, ram_q, rom_q))
        bus_trace.append((t, bus))

        # edges (level rise of gated clocks)
        if g_rom and not prev_g_rom:
            new_out = rom_mem.get(rom_addr_reg, 'X'*8)
            new_addr = A
            rom_out_reg, rom_addr_reg = new_out, new_addr
        if g_ram and not prev_g_ram:
            # RAM write with post-input-settle values (Verilog zero-delay)
            if write:
                ram[A] = clean_for_reg(bus)
            ram_addr_reg = A
            # buffer shift
            chain = [clean_for_reg(result)] + chain[:5]
        prev_g_rom, prev_g_ram = g_rom, g_ram

    return ram, chain, log, bus_trace

def report(tag, sigs, dur, rom_mem, ram_mem):
    ram, chain, log, bus_trace = simulate(sigs, dur, rom_mem, ram_mem)
    print('=' * 70)
    print(tag)
    print('-' * 70)
    rom_dump = {a: rom_mem[a] for a in sorted(rom_mem)}
    interesting = list(range(0x00, 0x10)) + list(range(0x30, 0x3E))
    print('RAM dump (interesting cells):')
    for a in interesting:
        print('  [%02X]=%s' % (a, b2h(ram.get(a, '??' * 4))), end='')
        if (a + 1) % 4 == 0: print()
    print()
    print('buffer chain r5..r0 (tail..head):', [b2h(c) for c in chain[::-1]])
    return ram, chain

if __name__ == '__main__':
    base = '/home/user/quart/lab3'
    rom_mem = mif_load(base + '/rom.mif')
    ram_mem = mif_load(base + '/ram.mif')

    sigs_cur, dur = parse_vwf_inputs(base + '/Block1.vwf')
    report('CURRENT Block1.vwf (Write rises 658.884 ns, glitch)', sigs_cur, dur, rom_mem, ram_mem)

    sigs_ori, dur = parse_vwf_inputs(base + '/db/Block1.sim_ori.vwf')
    report('LAST SIMULATED sim_ori.vwf (Write rises 669.942 ns)', sigs_ori, dur, rom_mem, ram_mem)
