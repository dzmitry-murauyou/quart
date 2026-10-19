#!/usr/bin/env python3
"""ONE-SHOT: add outclock pin to lpm_ram_dq0 (present but UNCONNECTED).
Per megafunction semantics: output is asynchronous when the outclock
port is not connected. Lab requirement: clock input on ROM AND RAM
must be split into inclock/outclock pins.
Touches: lpm_ram_dq0.v, _bb.v, _syn.v, .bsf, Block1.bdf (inline symbol).
"""
import sys

def sub1(s, old, new, what):
    assert s.count(old) == 1, f'{what}: found {s.count(old)} copies'
    return s.replace(old, new, 1)

PORTLIST_OLD = "module lpm_ram_dq0 (\n\taddress,\n\tdata,\n\tinclock,\n\twren,\n\tq);"
PORTLIST_NEW = "module lpm_ram_dq0 (\n\taddress,\n\tdata,\n\tinclock,\n\toutclock,\n\twren,\n\tq);"
PORTLIST_SYN_OLD = ("module lpm_ram_dq0 (\n\taddress,\n\tdata,\n\tinclock,\n\twren,\n"
                    "\tq)/* synthesis synthesis_clearbox = 1 */;")
PORTLIST_SYN_NEW = ("module lpm_ram_dq0 (\n\taddress,\n\tdata,\n\tinclock,\n\toutclock,\n"
                    "\twren,\n\tq)/* synthesis synthesis_clearbox = 1 */;")
DECL_OLD = "\tinput\t  inclock;\n\tinput\t  wren;"
DECL_NEW = "\tinput\t  inclock;\n\tinput\t  outclock;\n\tinput\t  wren;"
UP_OLD = "// Retrieval info: USED_PORT: inclock 0 0 0 0 INPUT NODEFVAL inclock\n"
UP_NEW = UP_OLD + "// Retrieval info: USED_PORT: outclock 0 0 0 0 INPUT NODEFVAL outclock\n"
CN_OLD = "// Retrieval info: CONNECT: @clock0 0 0 0 0 inclock 0 0 0 0\n"
CN_NEW = CN_OLD + "// Retrieval info: CONNECT: @clock1 0 0 0 0 outclock 0 0 0 0\n"

# ---- 1. simulation wrapper: expose outclock, route to clock1 ----
p = 'lab3/lpm_ram_dq0.v'
s = open(p, encoding='utf-8').read()
s = sub1(s, PORTLIST_OLD, PORTLIST_NEW, p + ' portlist')
s = sub1(s, DECL_OLD, DECL_NEW, p + ' decl')
s = sub1(s, "\t\t\t\t.clock1 (1'b1),", "\t\t\t\t.clock1 (outclock),", p + ' clock1')
s = sub1(s, UP_OLD, UP_NEW, p + ' used_port')
s = sub1(s, CN_OLD, CN_NEW, p + ' connect')
open(p, 'w', encoding='utf-8').write(s)

# ---- 2. blackbox ----
p = 'lab3/lpm_ram_dq0_bb.v'
s = open(p, encoding='utf-8').read()
s = sub1(s, PORTLIST_OLD, PORTLIST_NEW, p + ' portlist')
s = sub1(s, DECL_OLD, DECL_NEW, p + ' decl')
open(p, 'w', encoding='utf-8').write(s)

# ---- 3. synthesis wrapper (clearbox: port unused, must exist for match) ----
p = 'lab3/lpm_ram_dq0_syn.v'
s = open(p, encoding='utf-8').read()
s = sub1(s, PORTLIST_SYN_OLD, PORTLIST_SYN_NEW, p + ' portlist')
s = sub1(s, DECL_OLD, DECL_NEW, p + ' decl')
s = sub1(s, UP_OLD, UP_NEW, p + ' used_port')
open(p, 'w', encoding='utf-8').write(s)

# ---- 4. symbol .bsf + 5. inline symbol in Block1.bdf: add port stub ----
PORT_BLOCK = ("\t(port\n"
              "\t\t(pt 0 80)\n"
              "\t\t(input)\n"
              "\t\t(text \"inclock\" (rect 0 0 38 14)(font \"Arial\" (font_size 8)))\n"
              "\t\t(text \"inclock\" (rect 26 74 58 87)(font \"Arial\" (font_size 8)))\n"
              "\t\t(line (pt 0 80)(pt 16 80)(line_width 1))\n"
              "\t)\n")
PORT_NEW = PORT_BLOCK + (
              "\t(port\n"
              "\t\t(pt 0 96)\n"
              "\t\t(input)\n"
              "\t\t(text \"outclock\" (rect 0 0 47 14)(font \"Arial\" (font_size 8)))\n"
              "\t\t(text \"outclock\" (rect 26 90 64 103)(font \"Arial\" (font_size 8)))\n"
              "\t\t(line (pt 0 96)(pt 16 96)(line_width 1))\n"
              "\t)\n")
for p in ('lab3/lpm_ram_dq0.bsf', 'lab3/Block1.bdf'):
    s = open(p, encoding='utf-8').read()
    s = sub1(s, PORT_BLOCK, PORT_NEW, p + ' symbol port')
    open(p, 'w', encoding='utf-8').write(s)

print('patched: lpm_ram_dq0.v/_bb.v/_syn.v/.bsf + Block1.bdf (outclock pin, unconnected)')
