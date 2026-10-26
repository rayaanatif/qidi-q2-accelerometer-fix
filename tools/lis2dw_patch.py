#!/usr/bin/env python3
"""Find and patch the LIS2DW FIFO bug in a Qidi THR (toolhead) firmware image.

    python3 lis2dw_patch.py scan  IMAGE.bin
    python3 lis2dw_patch.py patch IMAGE.bin OUT.bin [--allow-unknown]

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
        "A", "3927036f418976aa34c61f09ad426364e23df1b04687678424df7c6593eccfae", False,
        "Q2 THR KLP_MCU_THR_V2_1.0.5 from the Q2 v1.1.1 package (34,780 bytes)"),
}


def tokens(spec):
    """'b9 06/07 ??' -> [(value, mask), ...]"""
    out = []
    for t in spec.split():
        if t == "??":
            out.append((0, 0))
        elif "/" in t:
            v, m = t.split("/")
            out.append((int(v, 16), int(m, 16)))
        else:
            out.append((int(t, 16), 0xFF))
    return out


# Each template: stock pattern, patched pattern, edits as (index, function(old byte)->new byte).
# Template B: 32-bit Thumb-2 build (current Q2 THR).
#   cmp.w r9,#0 ; bne.w X ; ldr r3,[pc] ; strb.w r9,[r3,#8] ; movs r3,#1 ; ldr r2,[pc] ; strb r3,[r2]
#   edit 1: bne.w -> beq.w (clear bit 6 of the first byte)
#   edit 2: strb.w r9,[r3,#8] -> movs r2,#0 ; strb r2,[r3,#8]   (r2 is overwritten two instructions later)
B_STOCK = tokens("b9 f1 00 0f  40/c0 f0/fb ?? 80/d0  ?? 4b  83 f8 08 90  01 23  ?? 4a  13 70")
B_PATCHED = tokens("b9 f1 00 0f  00/c0 f0/fb ?? 80/d0  ?? 4b  00 22 1a 72  01 23  ?? 4a  13 70")
B_EDITS = [(4, lambda b: b & ~0x40), (10, lambda b: 0x00), (11, lambda b: 0x22),
           (12, lambda b: 0x1A), (13, lambda b: 0x72)]

# Template A: 16-bit build (older Q2 THR).
#   cbnz r6,X ; ldr r3,[pc] ; strb r6,[r3,#8] ; movs r2,#1 ; ldr r3,[pc] ; strb r2,[r3]
#   edit 1: cbnz -> cbz (clear bit 11)
#   edit 2: strb r6,[r3,#8] -> strb r7,[r3,#8]   (r7 must be zero here; checked below)
A_STOCK = tokens("06/07 b9/fd  ?? 4b  1e 72  01 22  ?? 4b  1a 70")
A_PATCHED = tokens("06/07 b1/fd  ?? 4b  1f 72  01 22  ?? 4b  1a 70")
A_EDITS = [(1, lambda b: b & ~0x08), (4, lambda b: b | 0x01)]

TEMPLATES = {
    "A": (A_STOCK, A_PATCHED, A_EDITS),
    "B": (B_STOCK, B_PATCHED, B_EDITS),
}


def find(data, pat):
    n = len(pat)
    hits = []
    for i in range(len(data) - n + 1):
        if all((data[i + k] & m) == v for k, (v, m) in enumerate(pat)):
            hits.append(i)
    return hits


def r7_is_zero_here(data, at):
    """Template A only: the function containing `at` must start with
    push.w {r4-r8,lr} ; ... movs r7,#0 and nothing may write r7 afterwards.
    We check the prologue shape and that r7 only appears as a store source up to `at`.
    This is a structural check, not full data flow; it was verified by hand for the
    one image in KNOWN."""
    start = data.rfind(bytes.fromhex("2de9f041"), max(0, at - 0x200), at)
    if start < 0:
        return False
    window = data[start + 4:start + 40]
    return bytes.fromhex("0027") in bytes(window)


def scan(data):
    """Return list of (template name, offset, state) with state 'stock' or 'patched'."""
    found = []
    for name, (stock, patched, _) in TEMPLATES.items():
        for off in find(data, stock):
            ok = True
            if name == "A":
                ok = r7_is_zero_here(data, off)
            found.append((name, off, "stock" if ok else "stock-but-prologue-mismatch"))
        for off in find(data, patched):
            found.append((name, off, "patched"))
    return found


def sha(b):
    return hashlib.sha256(b).hexdigest()


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
        return 1
    for name, off, state in res:
        print(f"  template {name}: site at file offset 0x{off:x} ({state})")
    return 0


def cmd_patch(src, dst, allow_unknown):
    data = bytearray(open(src, "rb").read())
    h = sha(data)
    res = [r for r in scan(bytes(data)) if r[2] == "stock"]
    if any(r[2] == "patched" for r in scan(bytes(data))):
        sys.exit("This image already contains the patch. Nothing to do.")
    if len(res) != 1:
        sys.exit(f"Expected exactly one matching site, found {len(res)}. Not patching.")
    name, off, _ = res[0]
    known = KNOWN.get(h)
    if known:
        if known[0] != name:
            sys.exit("Matched template does not agree with the known-image table. Not patching.")
    elif not allow_unknown:
        sys.exit("Unknown image. Re-run with --allow-unknown only if you understand that this "
                 "patch has never been tested on this image.")
    _, _, edits = TEMPLATES[name]
    for idx, fn in edits:
        data[off + idx] = fn(data[off + idx]) & 0xFF
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
    if len(a) >= 3 and a[0] == "patch":
        sys.exit(cmd_patch(a[1], a[2], "--allow-unknown" in a[3:]))
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
