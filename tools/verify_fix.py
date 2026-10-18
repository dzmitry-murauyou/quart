#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the corrected .vwf stimulus for Block1 (RAM->RAM path)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_check import mif_load, simulate, b2h

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab3')
rom_mem = mif_load(base + '/rom.mif')
ram_mem = mif_load(base + '/ram.mif')


def tl_from_intervals(intervals, dur=860.0):
    out = []
    covered = 0.0
    for lvl, t0, t1 in intervals:
        assert abs(t0 - covered) < 1e-9, (t0, covered)
        out.append((t0, str(lvl)))
        covered = t1
    assert abs(covered - dur) < 1e-9
    return out


# address (decimal) schedule
addr_sched = [
    (3, 0, 80), (4, 80, 100), (5, 100, 120), (6, 120, 140), (7, 140, 160),
    (8, 160, 260),
    (48, 260, 280), (49, 280, 300), (50, 300, 320), (51, 320, 340),
    (52, 340, 360), (53, 360, 420),
    (10, 420, 460), (11, 460, 480), (12, 480, 500), (13, 500, 520),
    (14, 520, 540), (15, 540, 600),
    (56, 600, 640), (57, 640, 660), (58, 660, 680), (59, 680, 700),
    (60, 700, 720), (61, 720, 860),
]

clk_iv = []
for a in range(0, 860, 20):
    clk_iv.append((0, a, a + 10))
    clk_iv.append((1, a + 10, a + 20))

sigs = {
    'clk':     tl_from_intervals(clk_iv),
    'Read':    tl_from_intervals([(0, 0, 60), (1, 60, 220), (0, 220, 440),
                                  (1, 440, 580), (0, 580, 860)]),
    'Write':   tl_from_intervals([(0, 0, 260), (1, 260, 380), (0, 380, 620),
                                  (1, 620, 740), (0, 740, 860)]),
    'ROM_RAM': tl_from_intervals([(0, 0, 420), (1, 420, 860)]),
}
for b in range(6):
    iv = [((v >> b) & 1, t0, t1) for v, t0, t1 in addr_sched]
    sigs['Address[%d]' % b] = tl_from_intervals(iv)

ram, chain, log, bus_trace = simulate(sigs, 860.0, rom_mem, ram_mem, verbose_until=860.0)

print("RAM final dump:")
for a in list(range(0x00, 0x10)) + list(range(0x2E, 0x40)):
    print('  [%02X]=%s' % (a, b2h(ram.get(a, '????????'))), end='')
    if (a + 1) % 4 == 0:
        print()
print()
ok_rom = [b2h(ram.get(0x30 + i)) for i in range(6)] == ['11', '22', '33', '44', '55', '66']
ok_ram = [b2h(ram.get(0x38 + i)) for i in range(6)] == ['AA', 'BB', 'CC', 'DD', 'EE', 'FF']
ok_src = (b2h(ram.get(0x0F)) == 'FF' and
          [b2h(ram.get(0x0A + i)) for i in range(5)] == ['AA', 'BB', 'CC', 'DD', 'EE'])
print("ROM->RAM  0x30..0x35 = 11,22,33,44,55,66 :", ok_rom)
print("RAM->RAM  0x38..0x3D = AA,BB,CC,DD,EE,FF :", ok_ram)
print("source cells 0x0A..0x0F intact            :", ok_src)

# show what RAM q delivers during the RAM read window and what the buffer samples
print("\nGated-edge detail during RAM read [440,580) and write [620,740):")
for (t, clk, read, write, rrsel, A, g_rom, g_ram, bus, ram_q, rom_q) in log:
    pass  # log only kept when verbose_until>0; re-run with verbose instead below
