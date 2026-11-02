#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the phase-separated Quartus II 9.1 lab waveform.

Memory address changes occur 2 ns after falling edges, never at an active
memory clock edge. ROM output and RAM read address update on falling edges;
the buffer captures memory data on rising edges. RAM writes on rising edges,
while the buffer shifts on falling edges. Write deasserts before the final
falling edge so a previously-written byte cannot reappear on the data bus.
"""
import re, os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab3')
SRC = os.path.join(BASE, 'Block1.vwf')
DUR = 860.0

def tl(levels):
    """levels: list of (level, duration). Returns TRANSITION_LIST body."""
    assert abs(sum(d for _, d in levels) - DUR) < 1e-9, levels
    body = '\tNODE\n\t{\n\t\tREPEAT = 1;\n'
    for lvl, d in levels:
        body += '\t\tLEVEL %s FOR %s;\n' % (lvl, (('%g' % d) if d != int(d) else ('%d.0' % int(d))))
    body += '\t}'
    return body

NEW = {}
# clk: unchanged (kept from original file)
NEW['Read'] = tl([(0, 60), (1, 155), (0, 225), (1, 155), (0, 265)])
NEW['Write'] = tl([(0, 260), (1, 115), (0, 245), (1, 115), (0, 125)])
NEW['ROM_RAM'] = tl([(0, 420), (1, 440)])
# Addresses change away from the edges that clock either memory. Keep the
# first read address for two cycles while the valid pipeline fills.
address_changes = [
    (0, 3), (102, 4), (122, 5), (142, 6), (162, 7), (182, 8),
    (262, 48), (282, 49), (302, 50), (322, 51), (342, 52), (362, 53),
    (422, 10), (482, 11), (502, 12), (522, 13), (542, 14), (562, 15),
    (602, 56), (642, 57), (662, 58), (682, 59), (702, 60), (722, 61),
]
for bit in range(6):
    levels = []
    for i, (start, address) in enumerate(address_changes):
        end = address_changes[i + 1][0] if i + 1 < len(address_changes) else DUR
        level = (address >> bit) & 1
        if levels and levels[-1][0] == level:
            levels[-1] = (level, levels[-1][1] + end - start)
        else:
            levels.append((level, end - start))
    NEW['Address[%d]' % bit] = tl(levels)
# outputs: clear stale results -> Z for the whole run; the Quartus simulator
# re-fills them when the user presses "Start Simulation"
for sig in ['Data', 'ROM_out', 'RAM_out2']:
    for b in range(8):
        NEW['%s[%d]' % (sig, b)] = tl([('Z', DUR)])

def main():
    txt = open(SRC, encoding='utf-8', errors='surrogateescape').read()

    # 1) replace transition lists
    for sig, body in NEW.items():
        pat = re.compile(r'(TRANSITION_LIST\("' + re.escape(sig) +
                         r'"\)\n)\{.*?\n\}', re.S)
        txt, n = pat.subn(lambda m: m.group(1) + '{\n' + body + '\n}', txt, count=1)
        assert n == 1, 'transition list not found: %s' % sig

    # 2) unify bus radix to Hexadecimal (lab requirement: SHA/ShD one form)
    def fix_radix(m):
        blk = m.group(0)
        if 'ROM_out' in blk or 'RAM_out2' in blk:
            blk = blk.replace('RADIX = ASCII', 'RADIX = Hexadecimal')
        return blk
    txt = re.sub(r'DISPLAY_LINE\n\{.*?\n\}', fix_radix, txt, flags=re.S)

    # 3) put the time bar at the start of the RAM read phase
    txt = re.sub(r'TIME_BAR\n\{\n\tTIME = \d+;', 'TIME_BAR\n{\n\tTIME = 440000;', txt)

    open(SRC, 'w', encoding='utf-8', errors='surrogateescape').write(txt)
    print('Block1.vwf rewritten OK')

if __name__ == '__main__':
    main()
