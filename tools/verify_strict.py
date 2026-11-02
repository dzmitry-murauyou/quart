#!/usr/bin/env python3
"""Idealized event-level check of Block1.vwf and the split-phase buffer clock.

The structural wiring is checked separately by check_bdf.py. This model is not
Quartus: gate/clock-to-Q delays and the exact delta-cycle ordering are omitted.
It must not be used as a substitute for functional or timing simulation.
"""
from sim_check import mif_load, parse_vwf_inputs, value_at, b2h, clean_for_reg


def main():
    sig, duration = parse_vwf_inputs('lab3/Block1.vwf')
    rom, ram = mif_load('lab3/rom.mif'), mif_load('lab3/ram.mif')
    times = sorted({t for values in sig.values() for t, _ in values if t <= duration})
    chain = ['00000000'] * 6
    ra = 0
    rq = rom[ra]
    ma = 0
    rd1 = rd2 = 0
    write_armed = 0
    previous_clk = 0
    previous_rom_clk = 0
    previous_buffer_clk = 0
    writes, shifts, bad_changes, address_changes = [], [], [], []
    old_addr = None
    prev_write = 0

    for t in times:
        clk, read, write, sel = (int(value_at(sig[n], t)) for n in ('clk', 'Read', 'Write', 'ROM_RAM'))
        addr = int(''.join(value_at(sig['Address[%d]' % b], t) for b in range(5, -1, -1)), 2)
        if old_addr is not None and old_addr != addr:
            address_changes.append(t)
        old_addr = addr
        rising = clk and not previous_clk
        falling = not clk and previous_clk
        if write and not prev_write and clk:
            bad_changes.append(t)
        rom_valid = read and not sel and rd2
        ram_valid = read and sel and rd1
        read_pin = rom_valid or ram_valid
        buf_clk = (clk and read_pin) or ((not clk) and write and write_armed)
        sample = chain[5] if write else (rq if rom_valid else ram.get(ma, 'XXXXXXXX'))
        if buf_clk and not previous_buffer_clk:
            chain = [clean_for_reg(sample)] + chain[:5]
            shifts.append((t, 'write' if write else 'read', b2h(sample), 'fall' if falling else 'rise' if rising else 'other'))
        # All memories observe the same old state at a rising edge.
        old_ra = ra
        if clk and read and not previous_rom_clk:
            ra = addr
        if rising:
            rq = rom.get(old_ra, 'XXXXXXXX')
            if write:
                data = chain[5]
                ram[addr] = data
                writes.append((t, addr, b2h(data)))
            ma = addr
            rd1, rd2 = read, rd1
            write_armed = write
        # A read-valid DFF can enable the gated clock during the same high phase.
        read_after = read and ((not sel and rd2) or (sel and rd1))
        buf_after = (clk and read_after) or ((not clk) and write and write_armed)
        if buf_after and not buf_clk:
            sample = rq if not sel else ram.get(ma, 'XXXXXXXX')
            chain = [clean_for_reg(sample)] + chain[:5]
            shifts.append((t, 'read-valid', b2h(sample), 'delta'))
        previous_buffer_clk = buf_after
        previous_rom_clk = clk and read
        previous_clk, prev_write = clk, write

    expected = list(zip(range(0x30, 0x36), ['11','22','33','44','55','66'])) + list(zip(range(0x38, 0x3e), ['AA','BB','CC','DD','EE','FF']))
    checks = {
        'Write assertions occur during clk low': not bad_changes,
        'address stable at least 8 ns before each RAM write': all(
            not any(t - 8 < a <= t for a in address_changes) for t, _, _ in writes),
        '12 RAM writes in correct address/data order': [(a, d) for _, a, d in writes] == expected,
        'all buffer shifts during Write occur on falling clk': all(edge == 'fall' for _, phase, _, edge in shifts if phase == 'write'),
        '10 falling-edge shifts and no final unwanted shift': sum(phase == 'write' for _, phase, _, _ in shifts) == 10,
        'RAM source bytes remain intact': [b2h(ram[a]) for a in range(10,16)] == ['AA','BB','CC','DD','EE','FF'],
        'RAM cell 0 is FF': b2h(ram[0]) == 'FF',
    }
    for name, result in checks.items(): print(('PASS ' if result else 'FAIL ') + name)
    print('RAM writes:', writes)
    print('Buffer clock events:', shifts)
    print('NOTE: read-valid clock gating may create a delta-cycle edge; verify in Quartus.')
    return 0 if all(checks.values()) else 1

if __name__ == '__main__':
    raise SystemExit(main())
