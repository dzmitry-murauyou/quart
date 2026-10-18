#!/usr/bin/env python3
"""Patch lab3/Block1.bdf: add RD1/RD2 strobe DFFs (lpm_dff1), validity ANDs,
OR + final AND for buffer read pin; rewire bustri4/5 enabledt and buffer read."""
import re, sys

P = 'lab3/Block1.bdf'
s = open(P, encoding='utf-8').read()
orig = s

def conn(a, b):
    return "(connector\n\t(pt %d %d)\n\t(pt %d %d)\n)\n" % (a[0], a[1], b[0], b[1])

# ---------- 1. delete obsolete connectors ----------
DELETE = [
    ((920, 400), (1080, 400)),
    ((1080, 400), (1080, 296)),
    ((920, 416), (1016, 416)),
    ((1016, 416), (1016, 464)),
    ((1016, 464), (1136, 464)),
    ((1136, 464), (1136, 456)),
    ((760, 688), (976, 688)),
    ((760, 432), (760, 688)),
]
for a, b in DELETE:
    blk = conn(a, b)
    assert blk in s, 'connector not found: %s %s' % (a, b)
    s = s.replace(blk, '', 1)

# ---------- 2. add symbols ----------
def and2(name, x, y):
    return """(symbol
\t(rect %d %d %d %d)
\t(text "AND2" (rect 1 0 25 10)(font "Arial" (font_size 6)))
\t(text "%s" (rect 3 37 26 49)(font "Arial" ))
\t(port
\t\t(pt 0 16)
\t\t(input)
\t\t(text "IN1" (rect 2 7 19 19)(font "Courier New" (bold))(invisible))
\t\t(text "IN1" (rect 2 7 19 19)(font "Courier New" (bold))(invisible))
\t\t(line (pt 0 16)(pt 14 16)(line_width 1))
\t)
\t(port
\t\t(pt 0 32)
\t\t(input)
\t\t(text "IN2" (rect 2 23 19 35)(font "Courier New" (bold))(invisible))
\t\t(text "IN2" (rect 2 23 19 35)(font "Courier New" (bold))(invisible))
\t\t(line (pt 0 32)(pt 14 32)(line_width 1))
\t)
\t(port
\t\t(pt 64 24)
\t\t(output)
\t\t(text "OUT" (rect 48 15 65 27)(font "Courier New" (bold))(invisible))
\t\t(text "OUT" (rect 48 15 65 27)(font "Courier New" (bold))(invisible))
\t\t(line (pt 42 24)(pt 64 24)(line_width 1))
\t)
\t(drawing
\t\t(line (pt 14 12)(pt 30 12)(line_width 1))
\t\t(line (pt 14 37)(pt 31 37)(line_width 1))
\t\t(line (pt 14 12)(pt 14 37)(line_width 1))
\t\t(arc (pt 31 37)(pt 30 12)(rect 18 12 43 37)(line_width 1))
\t)
)
""" % (x, y, x + 64, y + 48, name)

def or2(name, x, y):
    return """(symbol
\t(rect %d %d %d %d)
\t(text "OR2" (rect 1 0 19 10)(font "Arial" (font_size 6)))
\t(text "%s" (rect 3 37 26 49)(font "Arial" ))
\t(port
\t\t(pt 0 32)
\t\t(input)
\t\t(text "IN2" (rect 2 23 19 35)(font "Courier New" (bold))(invisible))
\t\t(text "IN2" (rect 2 23 19 35)(font "Courier New" (bold))(invisible))
\t\t(line (pt 0 32)(pt 15 32)(line_width 1))
\t)
\t(port
\t\t(pt 0 16)
\t\t(input)
\t\t(text "IN1" (rect 2 7 19 19)(font "Courier New" (bold))(invisible))
\t\t(text "IN1" (rect 2 7 19 19)(font "Courier New" (bold))(invisible))
\t\t(line (pt 0 16)(pt 15 16)(line_width 1))
\t)
\t(port
\t\t(pt 64 24)
\t\t(output)
\t\t(text "OUT" (rect 48 15 65 27)(font "Courier New" (bold))(invisible))
\t\t(text "OUT" (rect 48 15 65 27)(font "Courier New" (bold))(invisible))
\t\t(line (pt 48 24)(pt 64 24)(line_width 1))
\t)
\t(drawing
\t\t(line (pt 14 36)(pt 25 36)(line_width 1))
\t\t(line (pt 14 13)(pt 25 13)(line_width 1))
\t\t(arc (pt 7 29)(pt 7 19)(rect -14 8 19 41)(line_width 1))
\t\t(arc (pt 49 24)(pt 25 13)(rect -6 13 57 76)(line_width 1))
\t\t(arc (pt 25 35)(pt 49 24)(rect -6 -27 57 36)(line_width 1))
\t)
)
""" % (x, y, x + 64, y + 48, name)

def dff1(name, x, y):
    return """(symbol
\t(rect %d %d %d %d)
\t(text "lpm_dff1" (rect 32 1 64 13)(font "Arial" (font_size 8)))
\t(text "%s" (rect 3 37 26 49)(font "Arial" ))
\t(port
\t\t(pt 0 16)
\t\t(input)
\t\t(text "data" (rect 0 0 24 12)(font "Arial" (font_size 8)))
\t\t(text "data" (rect 20 10 40 22)(font "Arial" (font_size 8)))
\t\t(line (pt 0 16)(pt 16 16)(line_width 1))
\t)
\t(port
\t\t(pt 0 32)
\t\t(input)
\t\t(text "clock" (rect 0 0 29 12)(font "Arial" (font_size 8)))
\t\t(text "clock" (rect 26 26 49 38)(font "Arial" (font_size 8)))
\t\t(line (pt 0 32)(pt 16 32)(line_width 1))
\t)
\t(port
\t\t(pt 96 32)
\t\t(output)
\t\t(text "q" (rect 0 0 8 12)(font "Arial" (font_size 8)))
\t\t(text "q" (rect 79 26 87 38)(font "Arial" (font_size 8)))
\t\t(line (pt 96 32)(pt 80 32)(line_width 1))
\t)
\t(drawing
\t\t(text "DFF" (rect 61 13 80 25)(font "Arial" ))
\t\t(line (pt 16 8)(pt 80 8)(line_width 1))
\t\t(line (pt 80 8)(pt 80 40)(line_width 1))
\t\t(line (pt 80 40)(pt 16 40)(line_width 1))
\t\t(line (pt 16 40)(pt 16 8)(line_width 1))
\t\t(line (pt 16 26)(pt 22 32)(line_width 1))
\t\t(line (pt 22 32)(pt 16 38)(line_width 1))
\t)
)
""" % (x, y, x + 96, y + 48, name)

SYMS = dff1('inst9', 784, 736) + dff1('inst10', 784, 792) \
     + and2('inst11', 1180, 760) + and2('inst12', 1180, 816) \
     + or2('inst13', 1280, 784) + and2('inst14', 1280, 840)

# insert symbols before the first "(connector"
i = s.index('(connector\n')
s = s[:i] + SYMS + s[i:]

# ---------- 3. add connectors ----------
WIRES = [
    # Read -> RD1.data  (tap off existing Read net at (488,688))
    ((488, 688), (488, 752)), ((488, 752), (784, 752)),
    # Read -> inst14.IN2 (branch at (700,752))
    ((700, 752), (700, 872)), ((700, 872), (1280, 872)),
    # clk -> RD1.clock / RD2.clock (tap off clk vertical (688,592)-(688,672))
    ((688, 640), (756, 640)), ((756, 640), (756, 824)),
    ((756, 768), (784, 768)), ((756, 824), (784, 824)),
    # RD1.q -> RD2.data
    ((880, 768), (904, 768)), ((904, 768), (904, 788)),
    ((904, 788), (872, 788)), ((872, 788), (872, 864)),
    ((872, 864), (744, 864)), ((744, 864), (744, 808)), ((744, 808), (784, 808)),
    # RD1.q -> inst12.IN2
    ((904, 768), (912, 768)), ((912, 768), (912, 848)), ((912, 848), (1180, 848)),
    # RD2.q -> inst11.IN2
    ((880, 824), (908, 824)), ((908, 824), (908, 792)), ((908, 792), (1180, 792)),
    # eq0 -> inst11.IN1
    ((920, 400), (948, 400)), ((948, 400), (948, 776)), ((948, 776), (1180, 776)),
    # eq1 -> inst12.IN1
    ((920, 416), (924, 416)), ((924, 416), (924, 832)), ((924, 832), (1180, 832)),
    # inst11.OUT -> OR13.IN1 and bustri4.enabledt
    ((1244, 784), (1264, 784)), ((1264, 784), (1264, 800)), ((1264, 800), (1280, 800)),
    ((1264, 784), (1264, 744)), ((1264, 744), (956, 744)),
    ((956, 744), (956, 336)), ((956, 336), (1080, 336)), ((1080, 336), (1080, 296)),
    # inst12.OUT -> OR13.IN2 and bustri5.enabledt
    ((1244, 840), (1264, 840)), ((1264, 840), (1264, 816)), ((1264, 816), (1280, 816)),
    ((1252, 840), (1252, 880)), ((1252, 880), (1136, 880)), ((1136, 880), (1136, 456)),
    # OR13.OUT -> inst14.IN1
    ((1344, 808), (1376, 808)), ((1376, 808), (1376, 856)), ((1376, 856), (1280, 856)),
    # inst14.OUT -> buffer read pin (976,688)
    ((1344, 864), (1392, 864)), ((1392, 864), (1392, 900)),
    ((1392, 900), (964, 900)), ((964, 900), (964, 688)), ((964, 688), (976, 688)),
]
add = ''.join(conn(a, b) for a, b in WIRES)

JUNC = [(488, 688), (700, 752), (688, 640), (756, 768), (904, 768), (1264, 784), (1252, 840)]
add += ''.join('(junction (pt %d %d))\n' % j for j in JUNC)

# append connectors+junctions at end of file
s = s.rstrip('\n') + '\n' + add
open(P, 'w', encoding='utf-8').write(s)
print('Block1.bdf patched: -%d connectors, +%d symbols-wires, +%d junctions'
      % (len(DELETE), len(WIRES), len(JUNC)))
