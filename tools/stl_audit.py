"""Offline binary-STL / Wavefront-OBJ diagnostics; never repairs or changes
input geometry.

Exact coordinate equality is used (no silent welding/tolerance). Edge topology
is not a self-intersection test. Signed volume is the sum of oriented triangle
contributions, NOT a union volume when shells overlap. STL/OBJ have no unit
metadata; R2's caller convention is millimetres. Runtime independent of printer
services.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import struct


def inspect_stl(path):
    path = Path(path)
    with path.open('rb') as stream:
        header = stream.read(84)
        if len(header) != 84:
            raise ValueError('truncated binary STL header')
        count = struct.unpack_from('<I', header, 80)[0]
        if path.stat().st_size != 84 + count * 50:
            raise ValueError('triangle count does not match file length')
        if not count:
            raise ValueError('empty mesh')
        low, high = [math.inf] * 3, [-math.inf] * 3
        edges, directed, faces = Counter(), Counter(), Counter()
        parents = {}
        degenerate = normal_errors = 0
        volume_terms = []

        def find(vertex):
            parents.setdefault(vertex, vertex)
            while parents[vertex] != vertex:
                parents[vertex] = parents[parents[vertex]]
                vertex = parents[vertex]
            return vertex

        for _ in range(count):
            values = struct.unpack('<12fH', stream.read(50))
            if not all(math.isfinite(v) for v in values[:12]):
                raise ValueError('non-finite coordinate or normal')
            normal = values[:3]
            a, b, c = values[3:6], values[6:9], values[9:12]
            for vertex in (a, b, c):
                for axis in range(3):
                    low[axis] = min(low[axis], vertex[axis])
                    high[axis] = max(high[axis], vertex[axis])
            u = tuple(b[i] - a[i] for i in range(3))
            v = tuple(c[i] - a[i] for i in range(3))
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            length = math.sqrt(sum(x*x for x in cross))
            if length == 0:
                degenerate += 1
            elif any(abs(normal[i] - cross[i]/length) > 1e-5 for i in range(3)):
                normal_errors += 1
            faces[tuple(sorted((a, b, c)))] += 1
            for start, end in ((a, b), (b, c), (c, a)):
                edges[tuple(sorted((start, end)))] += 1
                directed[start, end] += 1
                parents[find(end)] = find(start)
            volume_terms.append((a[0]*(b[1]*c[2]-b[2]*c[1]) +
                                 a[1]*(b[2]*c[0]-b[0]*c[2]) +
                                 a[2]*(b[0]*c[1]-b[1]*c[0])) / 6)
        boundary = sum(n == 1 for n in edges.values())
        nonmanifold = sum(n > 2 for n in edges.values())
        winding = sum(directed[a, b] != directed[b, a] for a, b in edges)
        return dict(triangles=count, bbox=[low, high],
                    signed_volume=math.fsum(volume_terms),
                    degenerate_faces=degenerate, normal_errors=normal_errors,
                    duplicate_faces=sum(n-1 for n in faces.values()),
                    boundary_edges=boundary, nonmanifold_edges=nonmanifold,
                    winding_errors=winding,
                    vertex_connected_components=len({find(v) for v in parents}),
                    self_intersections='not checked', units='mm (caller convention)')


def inspect_obj(path):
    """R2.14 (arena): diagnostics for a Wavefront OBJ (the object export since
    the STL removal). Parses the text 'v'/'f' records and computes the SAME
    metrics as inspect_stl - the OBJ carries the same triangles, vertex-deduped.
    Face records may carry 'v/vt/vn' slashes; only the vertex index is read."""
    path = Path(path)
    with path.open('r', encoding='utf-8', errors='replace') as stream:
        verts = []
        faces = []
        for raw in stream:
            line = raw.strip()
            if line.startswith('v '):
                parts = line[2:].split()
                if len(parts) < 3:
                    continue
                try:
                    verts.append(tuple(float(p) for p in parts[:3]))
                except ValueError:
                    continue
            elif line.startswith('f '):
                parts = line[2:].split()
                idx = []
                ok = True
                for tok in parts:
                    try:
                        idx.append(int(tok.split('/')[0]))
                    except ValueError:
                        ok = False
                        break
                if ok and len(idx) >= 3:
                    faces.append(tuple(idx))
    if not verts:
        raise ValueError('empty mesh (no vertices)')
    if not faces:
        raise ValueError('empty mesh (no faces)')
    low, high = [math.inf] * 3, [-math.inf] * 3
    edges, directed, face_count = Counter(), Counter(), Counter()
    parents = {}
    degenerate = normal_errors = 0
    volume_terms = []

    def find(vertex):
        parents.setdefault(vertex, vertex)
        while parents[vertex] != vertex:
            parents[vertex] = parents[parents[vertex]]
            vertex = parents[vertex]
        return vertex

    for f in faces:
        a, b, c = (verts[i - 1] for i in f[:3])   # OBJ indices are 1-based
        if not all(math.isfinite(coord) for vertex in (a, b, c)
                   for coord in vertex):
            raise ValueError('non-finite coordinate')
        for vertex in (a, b, c):
            for axis in range(3):
                low[axis] = min(low[axis], vertex[axis])
                high[axis] = max(high[axis], vertex[axis])
        u = tuple(b[i] - a[i] for i in range(3))
        v = tuple(c[i] - a[i] for i in range(3))
        cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        length = math.sqrt(sum(x*x for x in cross))
        if length == 0:
            degenerate += 1
        face_count[tuple(sorted((a, b, c)))] += 1
        for start, end in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((start, end)))] += 1
            directed[start, end] += 1
            parents[find(end)] = find(start)
        volume_terms.append((a[0]*(b[1]*c[2]-b[2]*c[1]) +
                             a[1]*(b[2]*c[0]-b[0]*c[2]) +
                             a[2]*(b[0]*c[1]-b[1]*c[0])) / 6)
    boundary = sum(n == 1 for n in edges.values())
    nonmanifold = sum(n > 2 for n in edges.values())
    winding = sum(directed[a, b] != directed[b, a] for a, b in edges)
    return dict(triangles=len(faces), bbox=[low, high],
                signed_volume=math.fsum(volume_terms),
                degenerate_faces=degenerate, normal_errors=normal_errors,
                duplicate_faces=sum(n-1 for n in face_count.values()),
                boundary_edges=boundary, nonmanifold_edges=nonmanifold,
                winding_errors=winding,
                vertex_connected_components=len({find(v) for v in parents}),
                self_intersections='not checked', units='mm (caller convention)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh')
    args = parser.parse_args()
    path = Path(args.mesh)
    if path.suffix.lower() == '.obj' or '.obj.' in path.name.lower():
        print(json.dumps(inspect_obj(path), indent=2))
    else:
        print(json.dumps(inspect_stl(path), indent=2))
