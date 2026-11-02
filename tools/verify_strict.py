#!/usr/bin/env python3
"""Event-level check of the current phase-separated lab stimulus.

This is an ideal, zero-delay model, not a Quartus simulation or a timing
analysis. Structural wiring is checked by check_bdf.py. RAM inputs change on
clock edges; in particular, its unregistered output follows registered address.
"""
from sim_check import mif_load, parse_vwf_inputs, value_at, b2h, clean_for_reg


def main():
    sig, duration = parse_vwf_inputs('lab3/Block1.vwf')
    rom, ram = mif_load('lab3/rom.mif'), mif_load('lab3/ram.mif')
    times = sorted({t for values in sig.values() for t, _ in values if t <= duration})
    chain = ['00000000'] * 6
    ra, rq, ma = 0, rom[0], 0
    rd1 = rd2 = read_ready = write_ready = 0
    old_clk = old_rom_clk = old_ram_clk = old_buf_clk = 0
    old_addr = None
    writes, shifts, active_memory_edges, addr_changes, bus_trace = [], [], [], [], []

    def val(name, t):
        return int(value_at(sig[name], t))

    def bus(read, write, sel):
        if read and read_ready:
            return ram.get(ma, 'XXXXXXXX') if sel else rq
        if write:
            return chain[5]
        return 'ZZZZZZZZ'

    for t in times:
        clk, read, write, sel = [val(n, t) for n in ('clk', 'Read', 'Write', 'ROM_RAM')]
        addr = sum(val('Address[%d]' % b, t) << b for b in range(6))
        if old_addr is not None and old_addr != addr:
            addr_changes.append(t)
        before = bus(read, write, sel)
        rom_clk = clk and read and not sel
        ram_clk = (clk and write) or ((not clk) and read and sel)
        valid = read and read_ready
        buf_clk = (clk and valid) or ((not clk) and write and write_ready)
        rising = clk and not old_clk
        falling = not clk and old_clk
        if buf_clk and not old_buf_clk:
            sample = clean_for_reg(before)
            shifts.append((t, 'write' if write else 'read', b2h(sample), 'fall' if falling else 'rise' if rising else 'other'))
            chain = [sample] + chain[:5]
        if rom_clk and not old_rom_clk:
            active_memory_edges.append((t, 'rom_in'))
            ra = addr
        if ram_clk and not old_ram_clk:
            active_memory_edges.append((t, 'ram_write' if write else 'ram_read'))
            if write:
                ram[addr] = clean_for_reg(before)
                writes.append((t, addr, b2h(before)))
            ma = addr
        if rising:
            rd1, rd2 = read, rd1
            write_ready = write
        if falling:
            rq = rom.get(ra, 'XXXXXXXX')
            read_ready = rd2
        # With the enable FF clocked on the opposite edge, changes to ready
        # must not create extra rising buffer-clock events after state settles.
        after_clk = (clk and read and read_ready) or ((not clk) and write and write_ready)
        if after_clk and not buf_clk:
            shifts.append((t, 'unexpected-delta', b2h(bus(read, write, sel)), 'delta'))
        after = bus(read, write, sel)
        bus_trace.append((t, b2h(after)))
        old_clk, old_rom_clk, old_ram_clk, old_buf_clk = clk, rom_clk, ram_clk, after_clk
        old_addr = addr

    expected_reads = ['11','22','33','44','55','66','AA','BB','CC','DD','EE','FF']
    expected_writes = list(zip(range(0x30, 0x36), expected_reads[:6])) + list(zip(range(0x38, 0x3e), expected_reads[6:]))
    reads = [x for x in shifts if x[1] == 'read']
    wshifts = [x for x in shifts if x[1] == 'write']
    edge_times = {t for t, _ in active_memory_edges}
    bus_map = dict(bus_trace)
    checks = {
        '12 RAM writes in correct address/data order': [(a, d) for _, a, d in writes] == expected_writes,
        '12 rising-edge buffer reads with exactly the expected bytes': [x[2] for x in reads] == expected_reads and all(x[3] == 'rise' for x in reads),
        '10 falling-edge buffer shifts during writes (no final extra shift)': len(wshifts) == 10 and all(x[3] == 'fall' for x in wshifts),
        'no extra or delta-cycle buffer clocks': all(x[3] in ('rise', 'fall') for x in shifts),
        'address changes never coincide with memory clock edges': not edge_times.intersection(addr_changes),
        'memory address is stable for at least 8 ns before each operation': all(
            not any(t-8 < a <= t for a in addr_changes) for t, _ in active_memory_edges),
        'each write has at least 8 ns address and data setup': all(
            not any(t-8 < a <= t for a in addr_changes) and
            len({v for when, v in bus_trace if t-9 <= when <= t}) <= 1
            for t, _, _ in writes),
        'each buffer read has at least 9 ns of stable bus data': all(
            len({v for when, v in bus_trace if t-9 <= when <= t}) <= 1 for t, _, _, _ in reads),
        'bus only carries expected bytes or high impedance': all(v in expected_reads or v == 'ZZZZZZZZ' for _, v in bus_trace),
        'no recycled byte after last writes': bus_map.get(375) == 'ZZZZZZZZ' and bus_map.get(380) == 'ZZZZZZZZ' and bus_map.get(735) == 'ZZZZZZZZ' and bus_map.get(740) == 'ZZZZZZZZ',
        'RAM source bytes remain intact': [b2h(ram[a]) for a in range(10,16)] == expected_reads[6:],
        'RAM cell 0 is FF': b2h(ram[0]) == 'FF',
    }
    for name, result in checks.items(): print(('PASS ' if result else 'FAIL ') + name)
    print('RAM writes:', writes)
    print('Buffer clock events:', shifts)
    print('Memory clock edges:', active_memory_edges)
    print('Address changes:', addr_changes)
    print('Bus trace:', bus_trace)
    print('NOTE: Quartus functional and timing simulation are still required.')
    return 0 if all(checks.values()) else 1

if __name__ == '__main__':
    raise SystemExit(main())
