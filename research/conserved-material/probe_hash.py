import modelA_stage03 as A
import exp5_surface as E
from common import gen_rock2
import random, math, sys

print("PYTHONHASHSEED:", __import__("os").environ.get("PYTHONHASHSEED"), file=sys.stderr)
verts, tris = gen_rock2(48)
ra = A.RockDensity(verts, tris, lattice=72, dfix=65536)
print("hash:", ra.hash_state())
rnd = random.Random(555)
orig, d = E.outside_ray(rnd)
res = ra.resolve_ray(orig, d)
o = tuple(c/65536 for c in orig)
ln = math.sqrt(sum(c*c for c in d)); dn = tuple(c/ln for c in d)
t = sum((res[0][j]/65536 - o[j])*dn[j] for j in range(3))
print("cell:", res[1], "t:", round(t,4))
