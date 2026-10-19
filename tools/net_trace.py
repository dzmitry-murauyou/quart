#!/usr/bin/env python3
"""Trace which symbol ports share the net of a given coordinate point."""
import re, sys

def parse(path):
    s = open(path, encoding='utf-8').read()
    syms = []
    for m in re.finditer(r'\(symbol\n\t\(rect (\d+) (\d+) (\d+) (\d+)\)\n'
                         r'\t\(text "([^"]+)"[^\n]*\n\t\(text "(inst[^"]*)"', s):
        x0, y0, x1, y1 = map(int, m.groups()[:4])
        sname, iname = m.group(5), m.group(6)
        body = s[m.end():s.index('\n)\n', m.end())]
        ports = {}
        for pm in re.finditer(r'\(port\n\t\t\(pt (\d+) (\d+)\)\n\t\t\((input|output|bidir)\)\n'
                              r'\t\t\(text "([^"]+)"', body):
            ports[pm.group(4)] = (x0 + int(pm.group(1)), y0 + int(pm.group(2)))
        syms.append((iname, sname, ports))
    conns = [((int(a), int(b)), (int(c), int(d))) for a, b, c, d in
             re.findall(r'\(connector\n(?:\t\(text [^\n]*\n)?\t\(pt (-?\d+) (-?\d+)\)\n\t\(pt (-?\d+) (-?\d+)\)', s)]
    juncs = [tuple(map(int, t)) for t in re.findall(r'\(junction \(pt (-?\d+) (-?\d+)\)\)', s)]
    return syms, conns, juncs

class DSU:
    def __init__(self): self.p = {}
    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]; a = self.p[a]
        return a
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb: self.p[ra] = rb

def on_seg(j, a, b):
    (x1, y1), (x2, y2) = a, b
    if (x1 == x2 == j[0]) and min(y1, y2) <= j[1] <= max(y1, y2): return True
    if (y1 == y2 == j[1]) and min(x1, x2) <= j[0] <= max(x1, x2): return True
    return False

def main(path, points):
    syms, conns, juncs = parse(path)
    d = DSU()
    for a, b in conns: d.union(a, b)
    for j in juncs:
        for a, b in conns:
            if (a == j or b == j or on_seg(j, a, b)):
                d.union(a, j); d.union(j, b)
    for label, pt in points:
        rn = d.find(pt)
        members = [(inm, sn, pn, p) for inm, sn, ports in syms
                   for pn, p in ports.items() if d.find(p) == rn]
        print(f'--- {label} {pt}: net members ---')
        for m in members: print('   ', m)
        # wire geometry of the net
        segs = [c for c in conns if d.find(c[0]) == rn]
        if not segs:
            print('    (no wires - pin present but unconnected)')
            continue
        xs = sorted({p[0] for s in segs for p in s})
        ys = sorted({p[1] for s in segs for p in s})
        print(f'    extent x[{min(xs)},{max(xs)}] y[{min(ys)},{max(ys)}]  segs={len(segs)}')

if __name__ == '__main__':
    main(sys.argv[1], eval(sys.argv[2]))
