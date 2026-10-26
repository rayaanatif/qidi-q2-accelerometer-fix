#!/usr/bin/env python3
"""Find and patch the LIS2DW FIFO bug in a Qidi THR (toolhead) firmware image.

    python3 lis2dw_patch.py scan  IMAGE.bin
    python3 lis2dw_patch.py patch IMAGE.bin OUT.bin [--allow-unknown]
    python3 lis2dw_patch.py fingerprint IMAGE.bin      (for images no template matches)

The bug (fixed upstream in Klipper commit 6269dda56bb7c08263153b18715d08e2d964bcab): the
accelerometer polling task sleeps when the FIFO still holds samples and re-runs
immediately when it is empty, so the effective rate is about 390 Hz instead of 1600 Hz.
Both fixes below make the same logical change: swap the two branches, and store a real
zero (not the sample count) in the scheduler flag on the "run again" path.

Instead of fixed offsets, the tool matches short instruction templates (Thumb-2) with
wildcards on the values that move between builds (branch distances, literal-pool offsets).
A template must match exactly once, or nothing is touched.

TRUST LEVELS
  * Image hash is in KNOWN and marked tested: verified on real hardware.
  * Image hash is in KNOWN and marked UNTESTED: the patch is derived and checked on paper
    only. Do not flash it unless you accept that risk and can recover the toolhead.
  * Unknown hash: `patch` refuses unless --allow-unknown, and the result has never been
    flashed anywhere. The scan only tells you the code *looks* the same.

This tool never flashes anything.
"""
import hashlib
import sys

# Known images: sha256 of stock -> (template name, sha256 of patched result, hardware tested?, label)
KNOWN = {
    "1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62": (
        "B", "9d2360ba47ebd720dbef07a0a4ebaf26004360bca090997d7b4a118c41460ac9", True,
        "Q2 THR 02.02.01.08 (35,056 bytes)"),
    "e114de22c629167381b68eb6e477b2a8dc93ee98fb2fbdb3c828f95a224c8f8b": (
        "A", "3927036f418976aa34c61f09ad426364e23df1b04687678424df7c6593eccfae", True,
        "Q2 THR KLP_MCU_THR_V2_1.0.5 from the Q2 v1.1.1 package (34,780 bytes)"),
}


def u16(d, i):
    return d[i] | (d[i + 1] << 8)


def is32(hw):
    return (hw >> 11) in (0b11101, 0b11110, 0b11111)


def writes16(hw):
    """Registers a 16-bit Thumb instruction may write (r0-r7/r8-r12; conservative)."""
    t = hw >> 13
    if t == 0b000:
        return {hw & 7}
    if t == 0b001:
        return set() if ((hw >> 11) & 3) == 1 else {(hw >> 8) & 7}
    if (hw >> 10) == 0b010000:
        return set() if ((hw >> 6) & 0xF) in (8, 10, 11) else {hw & 7}
    if (hw >> 10) == 0b010001:
        op = (hw >> 8) & 3
        if op == 1 or op == 3:
            return set()
        return {((hw >> 4) & 8) | (hw & 7)}
    if (hw >> 11) == 0b01001:
        return {(hw >> 8) & 7}
    if (hw >> 12) == 0b0101:
        return {hw & 7} if ((hw >> 9) & 7) >= 3 else set()
    if t == 0b011 or (hw >> 12) == 0b1000:
        return {hw & 7} if (hw >> 11) & 1 else set()
    if (hw >> 12) == 0b1001:
        return {(hw >> 8) & 7} if (hw >> 11) & 1 else set()
    if (hw >> 12) == 0b1010:
        return {(hw >> 8) & 7}
    if (hw >> 12) == 0b1011:
        if ((hw >> 9) & 7) == 0b110:
            return {i for i in range(8) if (hw >> i) & 1}
        if ((hw >> 8) & 0xF) in (0b0010, 0b1010):
            return {hw & 7}
        return set()
    if (hw >> 12) == 0b1100:
        w = {(hw >> 8) & 7}
        if (hw >> 11) & 1:
            w |= {i for i in range(8) if (hw >> i) & 1}
        return w
    return set()


def may_write32(h1, h2, reg):
    """Conservative: could this 32-bit instruction write `reg`?"""
    if (h1 >> 11) == 0b11110 and (h2 & 0x8000):      # b.w / b<cond>.w / bl: no data write
        return False
    if (h1 & 0xFF10) == 0xF800 and (h1 & 0x60) != 0x60:   # single store: Rt is a source
        return (h1 & 0xF) == reg                      # only the base could be written back
    return ((h2 >> 8) & 0xF) == reg or ((h2 >> 12) & 0xF) == reg


def range_may_write(data, lo, hi, reg):
    """Linear scan of [lo, hi): could any instruction write `reg`?"""
    i = lo
    while i < hi:
        hw = u16(data, i)
        if is32(hw):
            if may_write32(hw, u16(data, i + 2), reg):
                return True
            i += 4
        else:
            if reg in writes16(hw):
                return True
            i += 2
    return False


def find_B(data):
    """32-bit build (the tested Q2 image), any registers:
         cmp.w Rn,#0 ; bne.w X ; ldr Rt,[pc,#a] ; strb.w Rn,[Rt,#8] ;
         movs Ra,#1 ; ldr Rb,[pc,#b] ; strb Ra,[Rb]
       Rb is overwritten two instructions later, so it is a free scratch for the new zero store.
       Returns [(offset, state, regs)]."""
    out = []
    for i in range(len(data) - 19):
        b = data[i:i + 20]
        if not (b[1] == 0xF1 and 0xB0 <= b[0] <= 0xBC and b[2] == 0x00 and b[3] == 0x0F):
            continue
        rn = b[0] & 0xF
        h1 = b[4] | (b[5] << 8)
        h2 = b[6] | (b[7] << 8)
        if (h1 & 0xFBC0) not in (0xF040, 0xF000) or (h2 & 0xD000) != 0x8000:
            continue
        state = "stock" if (h1 & 0x03C0) == 0x0040 else "patched"
        if (h1 & 0x03C0) not in (0x0040, 0x0000):
            continue
        if not (0x48 <= b[9] <= 0x4F):
            continue
        rt = b[9] - 0x48
        if state == "stock":
            if not (b[10] == 0x80 | rt and b[11] == 0xF8 and b[12] == 0x08 and b[13] == rn << 4):
                continue
        else:
            # patched form: movs Rb,#0 ; strb Rb,[Rt,#8]
            if not (0x20 <= b[11] <= 0x27 and b[10] == 0x00
                    and b[13] == 0x72 and (b[12] & 0x38) >> 3 == rt):
                continue
        if not (b[14] == 0x01 and 0x20 <= b[15] <= 0x27):
            continue
        ra = b[15] - 0x20
        if not (0x48 <= b[17] <= 0x4F):
            continue
        rb = b[17] - 0x48
        if not (b[19] == 0x70 and b[18] == ((rb << 3) | ra)):
            continue
        if rt > 7 or rb > 7 or rb == rt or rb == ra:
            continue
        if state == "patched" and (b[11] - 0x20) != rb:
            continue
        out.append((i, state, {"Rn": rn, "Rt": rt, "Ra": ra, "Rb": rb}))
    return out


def edits_B(data, off, regs):
    rt, rb = regs["Rt"], regs["Rb"]
    e = {}
    e[off + 4] = data[off + 4] & ~0x40 & 0xFF                      # bne.w -> beq.w
    e[off + 10], e[off + 11] = 0x00, 0x20 + rb                     # movs Rb,#0
    e[off + 12], e[off + 13] = ((rt << 3) | rb) & 0xFF, 0x72       # strb Rb,[Rt,#8]
    return e


def find_A(data):
    """16-bit build (older Q2 image), any registers:
         cbnz Rn,X ; ldr Rt,[pc,#a] ; strb Rn,[Rt,#8] ; movs Ra,#1 ; ldr Rb,[pc,#b] ; strb Ra,[Rb]
       The fix stores zero from a register Rz that holds zero from the function prologue.
       Rz is found as `movs Rz,#0` shortly after `push.w {...}` and is accepted only if no
       instruction between that `movs` and the site can write it (conservative scan)."""
    out = []
    for i in range(len(data) - 11):
        b = data[i:i + 12]
        if (b[1] & 0xF5) != 0xB1:
            continue
        cbnz = bool(b[1] & 0x08)
        rn = b[0] & 7
        if not (0x48 <= b[3] <= 0x4F):
            continue
        rt = b[3] - 0x48
        hw = b[4] | (b[5] << 8)
        if (hw & 0xFFC0) != 0x7200 or ((hw >> 3) & 7) != rt:
            continue
        rs = hw & 7
        if not (b[6] == 0x01 and 0x20 <= b[7] <= 0x27):
            continue
        ra = b[7] - 0x20
        if not (0x48 <= b[9] <= 0x4F):
            continue
        rb = b[9] - 0x48
        if not (b[11] == 0x70 and b[10] == ((rb << 3) | ra)):
            continue
        if cbnz:
            if rs != rn:
                continue
            state = "stock"
        else:
            state = "patched"
        out.append((i, state, {"Rn": rn, "Rt": rt, "Rs": rs, "Ra": ra, "Rb": rb}))
    return out


def zero_register_for(data, site):
    """Return Rz (4..7) that provably (conservatively) holds zero at `site`, or None."""
    start = data.rfind(bytes.fromhex("2de9"), max(0, site - 0x400), site)
    while start >= 0:
        # push.w {..., lr}: 2d e9 lo hi
        pushed = u16(data, start + 2) if start + 3 < len(data) else 0
        z = None
        for k in range(start + 4, min(start + 44, site), 2):
            hw = u16(data, k)
            if (hw & 0xF8FF) == 0x2000 and 4 <= ((hw >> 8) & 7) <= 7 and (pushed >> ((hw >> 8) & 7)) & 1:
                z = (hw >> 8) & 7
                zpos = k
                break
        if z is not None and not range_may_write(data, zpos + 2, site, z):
            return z
        start = data.rfind(bytes.fromhex("2de9"), max(0, site - 0x400), start)
    return None


def edits_A(data, off, regs):
    z = zero_register_for(data, off)
    if z is None:
        return None
    e = {off + 1: data[off + 1] & ~0x08 & 0xFF}                    # cbnz -> cbz
    rt = regs["Rt"]
    e[off + 4] = ((8 << 6) | (rt << 3) | z) & 0xFF                 # strb Rz,[Rt,#8]
    e[off + 5] = 0x72
    return e


def scan(data):
    """Return [(template, offset, state, regs)]; state in stock / patched / stock-no-zero-reg."""
    found = []
    for off, state, regs in find_B(data):
        found.append(("B", off, state, regs))
    for off, state, regs in find_A(data):
        if state == "stock" and zero_register_for(data, off) is None:
            state = "stock-no-zero-reg"
        found.append(("A", off, state, regs))
    return found


def sha(b):
    return hashlib.sha256(b).hexdigest()


def embedded_version(data):
    """Version name stored in the image's Klipper identify block (zlib stream)."""
    import re
    import zlib
    for m in re.finditer(b"\x78[\x01\x5e\x9c\xda]", data):
        try:
            out = zlib.decompressobj().decompress(data[m.start():m.start() + 20000])
        except Exception:
            continue
        j = re.search(rb'"version":\s*"([^"]*)"', out)
        if j:
            return j.group(1).decode("ascii", "replace")
    return None


def anchors(data):
    """Register-agnostic anchors of the LIS2DW FIFO routine:
    `and Rd,Rn,#63` and `and Rd,Rn,#64` (32-bit), and `cmp Rn,#45` (16-bit) within 0x60 bytes."""
    a63 = [i for i in range(len(data) - 3)
           if data[i + 1] == 0xF0 and data[i] < 0x10 and data[i + 2] == 0x3F and data[i + 3] < 0x10]
    a64 = [i for i in range(len(data) - 3)
           if data[i + 1] == 0xF0 and data[i] < 0x10 and data[i + 2] == 0x40 and data[i + 3] < 0x10]
    c45 = [i for i in range(len(data) - 1) if data[i] == 0x2D and 0x28 <= data[i + 1] <= 0x2F]
    hits = []
    for i in a63:
        for j in a64:
            if abs(j - i) <= 0x40:
                for k in c45:
                    if abs(k - i) <= 0x60:
                        hits.append((min(i, j, k), i, j, k))
    return sorted(set(hits))


def cmd_fingerprint(path):
    data = open(path, "rb").read()
    print(f"file: {path}")
    print(f"size: {len(data)} bytes")
    print(f"sha256: {sha(data)}")
    print(f"embedded version: {embedded_version(data)}")
    print(f"known template match: {[(n, hex(o), st) for n, o, st, _ in scan(data)] or 'none'}")
    hits = anchors(data)
    if not hits:
        print("FIFO routine anchors: none found (different code; not the Klipper LIS2DW routine "
              "or compiled very differently)")
        return 1
    for lo, i, j, k in hits[:3]:
        start = max(0, lo - 16)
        blob = data[start:start + 176]
        print(f"FIFO routine anchors near 0x{lo:x}: and#63@0x{i:x} and#64@0x{j:x} cmp#45@0x{k:x}")
        print(f"hex dump from 0x{start:x} (post this when asking for a new template):")
        for off in range(0, len(blob), 16):
            print(f"  {start + off:06x}: " + blob[off:off + 16].hex(" "))
    return 0


def cmd_scan(path):
    data = open(path, "rb").read()
    h = sha(data)
    print(f"{path}: {len(data)} bytes, sha256 {h}")
    if h in KNOWN:
        t, out, tested, label = KNOWN[h]
        print(f"  known image: {label}; patched hash would be {out}")
        print("  hardware tested: " + ("YES" if tested else "NO (derived on paper only)"))
    else:
        print("  unknown image (not in the KNOWN table)")
    res = scan(data)
    if not res:
        print("  no matching bug site: this tool cannot patch this image")
        if anchors(data):
            print("  the LIS2DW FIFO routine looks present but compiled differently;")
            print("  run `fingerprint` on this image and post the output to get a template made")
        return 1
    for name, off, state, regs in res:
        regtxt = " ".join(f"{k}=r{v}" for k, v in regs.items())
        print(f"  template {name}: site at file offset 0x{off:x} ({state}; {regtxt})")
    return 0


def cmd_patch(src, dst, allow_unknown):
    data = bytearray(open(src, "rb").read())
    h = sha(data)
    allres = scan(bytes(data))
    if any(r[2] == "patched" for r in allres):
        sys.exit("This image already contains the patch. Nothing to do.")
    if any(r[2] == "stock-no-zero-reg" for r in allres):
        sys.exit("Site found, but no register provably holds zero there. Not patching.")
    res = [r for r in allres if r[2] == "stock"]
    if len(res) != 1:
        sys.exit(f"Expected exactly one matching site, found {len(res)}. Not patching.")
    name, off, _, regs = res[0]
    known = KNOWN.get(h)
    if known:
        if known[0] != name:
            sys.exit("Matched template does not agree with the known-image table. Not patching.")
    elif not allow_unknown:
        sys.exit("Unknown image. Re-run with --allow-unknown only if you understand that this "
                 "patch has never been tested on this image.")
    edits = edits_B(bytes(data), off, regs) if name == "B" else edits_A(bytes(data), off, regs)
    if edits is None:
        sys.exit("Could not determine a safe edit. Not patching.")
    for pos, val in edits.items():
        data[pos] = val & 0xFF
    out = bytes(data)
    if known and sha(out) != known[1]:
        sys.exit("Result hash differs from the expected patched image. Not writing.")
    open(dst, "wb").write(out)
    print(f"Wrote {dst} (template {name} at 0x{off:x})")
    print(f"  sha256 {sha(out)}")
    if known and not known[2]:
        print("  WARNING: this exact patch has NOT been tested on hardware.")
    if not known:
        print("  WARNING: unknown image; this patch has never been flashed or tested.")
    return 0


def main():
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "scan":
        sys.exit(cmd_scan(a[1]))
    if len(a) >= 2 and a[0] == "fingerprint":
        sys.exit(cmd_fingerprint(a[1]))
    if len(a) >= 3 and a[0] == "patch":
        sys.exit(cmd_patch(a[1], a[2], "--allow-unknown" in a[3:]))
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
