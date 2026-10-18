#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rewrite lab3/Block1.vwf with a corrected, glitch-free stimulus for
Quartus II 9.1 functional simulation (SIFO lab 3, variant 12).

Design facts (verified against lpm_rom0.v / lpm_ram_dq0.v / buffer_6byte.bdf):
  * clk period 20 ns, rising edges at 10+20k ns, falling edges at 20k ns.
  * ROM: address reg (inclock) + output reg (outclock) -> 2-cycle latency,
         clocked by clk & Read.
  * RAM: address reg (inclock), async output -> 1-cycle latency,
         clocked by clk & (Read|Write); wren = Write.
  * Buffer: 6-deep lpm_dff shift chain, same gated clock; shifts IN from
         the bus while Read, shifts OUT (tail r5) while Write.
  * All clocks are AND-gated -> Read/Write/ROM_RAM/Address must change
    ONLY when clk is LOW (at multiples of 20 ns), otherwise a spurious
    gated-clock edge corrupts RAM and the buffer.

Corrected schedule:
  [0,60)     idle (scheme does not start at 0 ns)
  [60,220)   READ from ROM (ROM_RAM=0), addresses 0x03..0x08, 8 gated edges:
             2 pipeline-fill + 6 data samples 11,22,33,44,55,66 -> buffer
  [220,260)  wait 2 clk
  [260,380)  WRITE buffer -> RAM addresses 0x30..0x35, 6 gated edges
  [380,440)  wait (ROM_RAM 0->1 at 420, address preset 0x0A)
  [440,580)  READ from RAM (ROM_RAM=1), addresses 0x0A..0x0F, 7 gated edges:
             1 pipeline-fill (stale q) + 6 data samples AA,BB,CC,DD,EE,FF
  [580,620)  wait 2 clk (address preset 0x38)
  [620,740)  WRITE buffer -> RAM addresses 0x38..0x3D, 6 gated edges
  [740,860)  idle
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
NEW['Read'] = tl([(0, 60), (1, 160), (0, 220), (1, 140), (0, 280)])
NEW['Write'] = tl([(0, 260), (1, 120), (0, 240), (1, 120), (0, 120)])
NEW['ROM_RAM'] = tl([(0, 420), (1, 440)])
NEW['Address[5]'] = tl([(0, 260), (1, 160), (0, 180), (1, 260)])
NEW['Address[4]'] = tl([(0, 260), (1, 160), (0, 180), (1, 260)])
NEW['Address[3]'] = tl([(0, 160), (1, 100), (0, 160), (1, 440)])
NEW['Address[2]'] = tl([(0, 80), (1, 80), (0, 180), (1, 80), (0, 60),
                        (1, 120), (0, 100), (1, 160)])
NEW['Address[1]'] = tl([(1, 80), (0, 40), (1, 40), (0, 140), (1, 40),
                        (0, 80), (1, 60), (0, 40), (1, 80), (0, 60),
                        (1, 40), (0, 160)])
NEW['Address[0]'] = tl([(1, 80), (0, 20), (1, 20), (0, 20), (1, 20),
                        (0, 120), (1, 20), (0, 20), (1, 20), (0, 20),
                        (1, 60), (0, 40), (1, 20), (0, 20), (1, 20),
                        (0, 20), (1, 60), (0, 40), (1, 20), (0, 20),
                        (1, 20), (0, 20), (1, 140)])
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
