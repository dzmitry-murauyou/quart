#!/usr/bin/env python3
"""ONE-SHOT: split ROM outclock onto its own net (raw clk).
Before: ROM inclock & outclock share one net (inst6 OUT = clk&Read).
After:  inclock  = clk&Read net (unchanged)
        outclock = raw top-level clk net, junction at (632,360)
Route: (792,296)->(768,296)->(768,360)->(632,360).
"""
import re, sys
sys.path.insert(0, 'tools')
from net_trace import parse, DSU, on_seg

PATH = 'lab3/Block1.bdf'
s = open(PATH, encoding='utf-8').read()
syms, conns, juncs = parse(PATH)

# --- 0. sanity: current state is the tied-net version ---
d = DSU()
for a, b in conns: d.union(a, b)
for j in juncs:
    for a, b in conns:
        if (a == j or b == j or on_seg(j, a, b)):
            d.union(a, j); d.union(j, b)
assert d.find((792, 280)) == d.find((792, 296)), 'ROM clocks already split?'
assert d.find((792, 280)) == d.find((704, 328)), 'inclock not on inst6 net?'
assert d.find((624, 288)) == d.find((632, 592)), 'clk net changed?'

# --- 1. intrusion scan for the 3 new segments against ALL symbol bodies ---
new_segs = [((792, 296), (768, 296)), ((768, 296), (768, 360)),
            ((768, 360), (632, 360))]
bodies = []
for m in re.finditer(r'\(symbol\n\t\(rect (\d+) (\d+) (\d+) (\d+)\)\n'
                     r'\t\(text "([^"]+)"[^\n]*\n\t\(text "(inst[^"]*)"', s):
    bodies.append((m.group(6), m.group(5), tuple(map(int, m.groups()[:4]))))
bad = []
for name, sn, (x0, y0, x1, y1) in bodies:
    for a, b in new_segs:
        if a[0] == b[0]:  # vertical
            x = a[0]; lo, hi = sorted((a[1], b[1]))
            if x0 < x < x1 and lo < y1 and hi > y0: bad.append((name, 'v', x))
        else:
            y = a[1]; lo, hi = sorted((a[0], b[0]))
            if y0 < y < y1 and lo < x1 and hi > x0: bad.append((name, 'h', y))
assert not bad, f'intrusion: {bad}'

# --- 2. no unintended T-touches / overlaps with other nets ---
deleted = [((792, 296), (760, 296)), ((760, 288), (760, 296))]
keep_conns = [c for c in conns if c not in deleted and (c[1], c[0]) not in deleted]
def touches(p, seg):
    (x1, y1), (x2, y2) = seg
    return (x1 == x2 == p[0] and min(y1, y2) <= p[1] <= max(y1, y2)) or \
           (y1 == y2 == p[1] and min(x1, x2) <= p[0] <= max(x1, x2))
endpoints = {p for c in keep_conns for p in c} | set(juncs)
my_pts = {(792, 296), (768, 296), (768, 360), (632, 360)}
for seg in new_segs:
    for p in endpoints - my_pts:
        if touches(p, seg):
            # allowed only at (632,360) junction on the clk net
            assert p == (632, 360) and d.find(p) == d.find((624, 288)), \
                f'new seg {seg} touches foreign point {p}'
# collinear overlap with existing same-orientation segments?
for a, b in new_segs:
    for c, e in keep_conns:
        if a[0] == b[0] == c[0] == e[0]:
            lo1, hi1 = sorted((a[1], b[1])); lo2, hi2 = sorted((c[1], e[1]))
            assert hi1 <= lo2 or hi2 <= lo1 or lo1 == hi1, f'overlap V {a}{b} vs {c}{e}'
        if a[1] == b[1] == c[1] == e[1]:
            lo1, hi1 = sorted((a[0], b[0])); lo2, hi2 = sorted((c[0], e[0]))
            assert hi1 <= lo2 or hi2 <= lo1 or lo1 == hi1, f'overlap H {a}{b} vs {c}{e}'

# --- 3. apply edits ---
def rm_connector(x1, y1, x2, y2):
    global s
    pat = ('(connector\n'
           f'\t(pt {x1} {y1})\n'
           f'\t(pt {x2} {y2})\n'
           ')\n')
    assert s.count(pat) == 1, f'connector not found/dup: {pat!r}'
    s = s.replace(pat, '', 1)

rm_connector(792, 296, 760, 296)   # old outclock stub
rm_connector(760, 288, 760, 296)   # old join vertical (lower half)
# (760,280)-(760,288) stays: inclock stub vertical

# junction (760,288) becomes a plain L-corner -> remove dot
pat = '(junction (pt 760 288))\n'
assert s.count(pat) == 1
s = s.replace(pat, '', 1)

# new outclock route: insert before the first junction block
new_conns = ('(connector\n\t(pt 792 296)\n\t(pt 768 296)\n)\n'
             '(connector\n\t(pt 768 296)\n\t(pt 768 360)\n)\n'
             '(connector\n\t(pt 768 360)\n\t(pt 632 360)\n)\n')
first_con = s.index('(connector\n')
s = s[:first_con] + new_conns + s[first_con:]

# junction where outclock taps the clk vertical x=632 (y 320..592)
pat = '(junction (pt 760 288))\n'  # already removed; anchor on next junction line
anchor = '(junction (pt 1224 384))'
assert s.count(anchor) == 1
s = s.replace(anchor, '(junction (pt 632 360))\n' + anchor, 1)

open(PATH, 'w', encoding='utf-8').write(s)
print('patched OK')
