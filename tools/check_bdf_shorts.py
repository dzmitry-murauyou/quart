#!/usr/bin/env python3
"""Detect shorted BDF wires, including collinear overlaps and T-junctions.

Unlike a check based only on explicit junction markers, wire endpoints that
lie on other segments are joined. Crossings in the middle of both segments
are joined only when marked with a junction. This is a conservative geometry
check, not a substitute for Quartus Analysis & Synthesis.
"""
import re
import sys
from check_bdf import DSU, on_seg, parse


def check(path):
    symbols, connectors, junctions = parse(path)
    text = open(path, encoding='utf-8').read()
    nets = DSU()
    for a, b in connectors:
        nets.union(a, b)
    for i, (a, b) in enumerate(connectors):
        for c, d in connectors[i + 1:]:
            if on_seg(a, c, d) or on_seg(b, c, d) or on_seg(c, a, b) or on_seg(d, a, b):
                nets.union(a, c)
    for point in junctions:
        for a, b in connectors:
            if on_seg(point, a, b):
                nets.union(point, a)

    def attach(point):
        for a, b in connectors:
            if on_seg(point, a, b):
                nets.union(point, a)

    for _, _, ports in symbols:
        for pt in ports.values():
            attach(pt)
    pin_inputs = []
    pin_pattern = r'\(pin\n\s*\(input\)\n\s*\(rect (-?\d+) (-?\d+) (-?\d+) (-?\d+)\).*?\(text "INPUT"[^\n]*\n\s*\(text "([^"]+)"[^\n]*\n\s*\(pt (-?\d+) (-?\d+)\)'
    for match in re.finditer(pin_pattern, text, re.S):
        x, y, _, _, name, dx, dy = match.groups()
        point = (int(x) + int(dx), int(y) + int(dy))
        attach(point)
        pin_inputs.append((name, point))

    drivers = {}
    for name, point in pin_inputs:
        drivers.setdefault(nets.find(point), []).append(name)
    for inst, symbol, ports in symbols:
        for name, point in ports.items():
            is_driver = ((symbol in ('AND2', 'OR2', 'NOT') and name == 'OUT') or
                         (symbol.startswith('lpm_dff') and name == 'q') or
                         (symbol.startswith('lpm_decode') and name.startswith('eq')))
            if is_driver:
                drivers.setdefault(nets.find(point), []).append(inst + '.' + name)
    conflicts = [group for group in drivers.values() if len(group) > 1]
    for group in conflicts:
        print('FAIL multiple drivers:', ', '.join(group))
    if not conflicts:
        print('PASS: no multiple scalar drivers detected in', path)
    return bool(conflicts)


if __name__ == '__main__':
    raise SystemExit(check(sys.argv[1] if len(sys.argv) > 1 else 'lab3/Block1.bdf'))
