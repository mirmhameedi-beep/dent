"""DENT Stage 0.2 — montage builder: side-by-side comparison sheets from
existing renders. Pure PNG tiling with common.FIX-preserving flip handling.
"""
import os, sys, math, struct, zlib

sys.path.insert(0, '.')


def read_png(path):
    with open(path, 'rb') as f:
        data = f.read()
    pos = 8; w = h = None; idat = b''
    while pos < len(data):
        ln = struct.unpack('>I', data[pos:pos+4])[0]
        typ = data[pos+4:pos+8]
        if typ == b'IHDR':
            w, h, bd, ct = struct.unpack('>IIBB', data[pos+8:pos+18])
        elif typ == b'IDAT':
            idat += data[pos+8:pos+8+ln]
        pos += 12 + ln
    raw = zlib.decompress(idat)
    bpp = {2: 3, 0: 1, 6: 4}.get(ct, 3)*{0:1,8:1}[bd]
    stride = w*bpp
    out = bytearray(w*h*bpp)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]; p += 1
        line = bytearray(raw[p:p+stride]); p += stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i-bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i-bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i-bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i-bpp] if i >= bpp else 0
                pa = abs(b-c); pb = abs(a-c); pc = abs(a+b-2*c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y*stride:(y+1)*stride] = line
        prev = line
    return w, h, bpp, bytes(out)


def write_png(path, w, h, bpp, pix):
    ct = {1: 0, 3: 2, 4: 6}[bpp]
    ib = z = b''
    stride = w*bpp
    for y in range(h):
        z += b'\x00' + pix[y*stride:(y+1)*stride]
    comp = zlib.compress(z, 6)

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t+d) & 0xFFFFFFFF)
    ib = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ct, 0, 0, 0))
          + chunk(b'IDAT', comp) + chunk(b'IEND', b''))
    open(path, 'wb').write(ib)


def tile(paths, out_path, cols=None, pad=8, scale=1):
    imgs = [read_png(p) for p in paths]
    n = len(imgs)
    if cols is None:
        cols = min(n, 3)
    rows = math.ceil(n/cols)
    if scale != 1:
        imgs = [_scale(im, scale) for im in imgs]
    cell_w = max(im[0] for im in imgs)
    cell_h = max(im[1] for im in imgs)
    bw = pad + cols*(cell_w+pad); bh = pad + rows*(cell_h+pad)
    canvas = bytearray(bw*bh*3)
    # dark background (matches Dent charcoal)
    for i in range(0, len(canvas), 3):
        canvas[i] = 18; canvas[i+1] = 18; canvas[i+2] = 20
    for idx, (w, h, bpp, px) in enumerate(imgs):
        r, c = divmod(idx, cols)
        ox = pad + c*(cell_w+pad); oy = pad + r*(cell_h+pad)
        for y in range(h):
            di = ((oy+y)*bw + ox)*3
            for x in range(w):
                si = (y*w + x)*bpp
                if bpp == 4 and px[si+3] == 0:
                    continue
                if bpp == 3:
                    canvas[di+x*3:di+x*3+3] = px[si:si+3]
                elif bpp == 4:
                    canvas[di+x*3:di+x*3+3] = px[si:si+3]
                else:  # grayscale
                    canvas[di+x*3] = canvas[di+x*3+1] = canvas[di+x*3+2] = px[si]
    write_png(out_path, bw, bh, 3, bytes(canvas))
    print(out_path, bw, "x", bh)


if __name__ == "__main__":
    O = "out/s02"
    import json, glob
    # sheet 1: progression
    if os.path.exists(f"{O}/LC_S30000_front.png"):
        avail = [f"{O}/{n}" for n in ("LC_PRISTINE_front.png", "LC_S100_front.png",
              "LC_S1000_front.png", "LC_S10000_front.png", "LC_S30000_front.png",
              "VS_cavity_interior_front.png")]
        tile([p for p in avail if os.path.exists(p)], "out/REPORT_progression.png", cols=3)
    # sheet 2: fracture set
    frs = [f"{O}/FR{i}_{n}_34.png" for i, n in
           ((1, "centre_face"), (2, "edge_line"), (3, "crevice_floor"),
            (4, "clusters"), (5, "distributed"), (6, "weakened_root"))]
    if all(os.path.exists(p) for p in frs):
        tile(frs, "out/REPORT_fractures.png", cols=3)
    # sheet 3: vis comparisons (built after s02_vis finishes)
    v1 = [f"{O}/VS_concentrated10k_front.png", f"{O}/VS_distributed10k_front.png"]
    if all(os.path.exists(p) for p in v1):
        tile(v1, "out/REPORT_equal10k.png", cols=2)
    des = sorted(glob.glob(f"{O}/VS_destroy_*pct_front.png"))
    if des:
        tile(des, "out/REPORT_destruction.png", cols=3)
