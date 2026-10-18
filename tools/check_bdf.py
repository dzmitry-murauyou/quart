#!/usr/bin/env python3
"""Structural connectivity audit for lab3 BDF netlists (Quartus II 9.1 format).
Mid-line crossings WITHOUT a junction do NOT connect; shared endpoints and
junction points do."""
import re, sys

def parse(path):
    s = open(path, encoding='utf-8').read()
    syms = []   # (instname, symbolname, {(portname or index): (x,y)})
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

def nets(path):
    syms, conns, juncs = parse(path)
    d = DSU()
    for a, b in conns:
        d.union(a, b)
    for j in juncs:
        first = None
        for a, b in conns:
            if (a == j or b == j or on_seg(j, a, b)):
                if first is None: first = (a, b)
                d.union(a, j); d.union(j, b)
    out = {}
    for iname, sname, ports in syms:
        for pn, pt in ports.items():
            out.setdefault((iname, sname), {})[pn] = d.find(pt)
    return out, d, syms, conns

def main():
    top, dtop, tsyms, tconn = nets('lab3/Block1.bdf')
    buf, dbuf, bsyms, bconn = nets('lab3/buffer_6byte.bdf')
    def T(inst): 
        for k, v in top.items():
            if k[0] == inst: return v
        raise KeyError(inst)
    def B(inst):
        for k, v in buf.items():
            if k[0] == inst: return v
        raise KeyError(inst)
    ok = True
    def chk(label, cond):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label)
        ok = ok and cond
    rd1, rd2, a11, a12, o13, a14 = T('inst9'), T('inst10'), T('inst11'), T('inst12'), T('inst13'), T('inst14')
    # locate reference nets by geometry of existing pins
    refs = {}
    for iname, sname, ports in tsyms:
        refs[(iname, sname)] = ports
    # Read input pin = INPUT symbol feeding (488,688); clk pin feeds (688,592..672)
    read_net = top[('inst9', 'lpm_dff1')]['data']
    clk_net = rd1['clock']
    chk('RD1.data == RD2? no; RD1.data net != clk net', read_net != clk_net)
    chk('RD1.clock == RD2.clock == clk', rd1['clock'] == rd2['clock'] == clk_net)
    chk('RD2.data == RD1.q', rd2['data'] == rd1['q'])
    chk('AND11.IN2 == RD2.q', a11['IN2'] == rd2['q'])
    chk('AND12.IN2 == RD1.q', a12['IN2'] == rd1['q'])
    chk('AND11.IN2 != AND12.IN1', a11['IN2'] != a12['IN1'])
    chk('AND12.IN2 != RD2.q', a12['IN2'] != rd2['q'])
    chk('AND11.IN1 != AND12.IN1 (eq0 != eq1)', a11['IN1'] != a12['IN1'])
    chk('AND11.OUT == bustri4 enabledt (1080,296 net) & OR13.IN1',
        a11['OUT'] == o13['IN1'])
    chk('AND12.OUT == OR13.IN2', a12['OUT'] == o13['IN2'])
    chk('OR13.OUT == AND14.IN1', o13['OUT'] == a14['IN1'])
    chk('AND14.IN2 == Read net', a14['IN2'] == read_net)
    # bustri4/5 enabledt ports: find lpm_bustri symbols on top
    b4 = [v for k, v in top.items() if k[0] == 'inst4'][0] if any(k[0]=='inst4' for k in top) else None
    names = {k[0]: k[1] for k in top}
    # find which top inst is bustri driving ROM (enabledt port at (1080,296))
    tgt4 = tgt5 = None
    for k, v in top.items():
        for pn, pt in v.items():
            if pt == (1080, 296): tgt4 = v[pn]
            if pt == (1136, 456): tgt5 = v[pn]
    chk('bustri4.enabledt net == AND11.OUT', tgt4 == a11['OUT'])
    chk('bustri5.enabledt net == AND12.OUT', tgt5 == a12['OUT'])
    # buffer read pin (976,688) == AND14.OUT
    tgtR = None
    for k, v in top.items():
        for pn, pt in v.items():
            if pt == (976, 688): tgtR = v[pn]
    chk('buffer.read pin net == AND14.OUT', tgtR == a14['OUT'])
    chk('buffer.read net != Read net', tgtR != read_net)
    chk('buffer.read net != clk net', tgtR != clk_net)
    # buffer write pin (976,704) untouched, distinct
    tgtW = None
    for k, v in top.items():
        for pn, pt in v.items():
            if pt == (976, 704): tgtW = v[pn]
    chk('buffer.write pin net distinct from read/clk', tgtW not in (tgtR, read_net, clk_net))
    # ---- buffer internal ----
    bst = B('inst14'); or16 = B('inst16'); and15 = B('inst15')
    rpin = dbuf.find((-8, 416)); wpin = dbuf.find((72, 448)); cpin = dbuf.find((72, 240))
    chk('buf: enabletr == OR16.OUT', bst.get('enabletr') == or16['OUT'] or
        (lambda: [v[pn] for k, v in buf.items() if k[0]=='inst14' for pn, pt in v.items() if pt==(632,408)])() == [or16['OUT']])
    etr = [v[pn] for k, v in buf.items() if k[0] == 'inst14' for pn, pt in v.items() if pt == (632, 408)]
    edt = [v[pn] for k, v in buf.items() if k[0] == 'inst14' for pn, pt in v.items() if pt == (632, 464)]
    chk('buf: enabletr(632,408) == OR16.OUT', etr == [or16['OUT']])
    chk('buf: enabledt(632,464) == write pin', edt == [wpin])
    chk('buf: OR16.IN1 == read pin', or16['IN1'] == rpin)
    chk('buf: OR16.IN2 == write pin', or16['IN2'] == wpin)
    chk('buf: AND15 = clk & OR16.OUT -> spine', and15['IN2'] == or16['OUT'] and and15['IN1'] == cpin)
    spine = [v[pn] for k, v in buf.items() if k[0] == 'inst10' for pn, pt in v.items() if pn == 'clock']
    chk('buf: DFF clocks == AND15.OUT', spine == [and15['OUT']])
    print('\nALL PASS' if ok else '\nFAILURES PRESENT')
    sys.exit(0 if ok else 1)

main()
