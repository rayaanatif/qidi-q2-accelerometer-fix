#!/usr/bin/env python3
"""Apply the LIS2DW FIFO fix to YOUR OWN stock Qidi THR (toolhead) image.

This repo does not ship any Qidi firmware. You read the stock image off your own
toolhead with the snapshot command (docs/GUIDE.md step 6), then run:

    python3 apply_patch.py thr-before/application.bin patched.bin

It refuses to continue unless the input is exactly the known stock image
(Qidi THR 02.02.01.08, 35,056 bytes) and the result is exactly the image the
upstream flashing tool admits. The two patch sites are from
https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized
(firmware/max4-thr-lis2dw-fifo-v1.json), which fixes the same bug fixed upstream in
Klipper commit 6269dda56bb7c08263153b18715d08e2d964bcab
"""
import hashlib
import sys

STOCK_SHA256 = "1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62"
PATCHED_SHA256 = "9d2360ba47ebd720dbef07a0a4ebaf26004360bca090997d7b4a118c41460ac9"
SIZE = 35056
PATCHES = [  # (offset, before, after)
    (0x0BFE, bytes.fromhex("40"), bytes.fromhex("00")),
    (0x0C04, bytes.fromhex("83f80890"), bytes.fromhex("00221a72")),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    data = bytearray(open(sys.argv[1], "rb").read())
    if len(data) != SIZE:
        sys.exit(f"Unexpected size {len(data)} (expected {SIZE}). Not patching.")
    if sha(data) != STOCK_SHA256:
        sys.exit("Input is not the known stock THR 02.02.01.08 image. Not patching.")
    for off, before, after in PATCHES:
        if bytes(data[off:off + len(before)]) != before:
            sys.exit(f"Unexpected bytes at 0x{off:x}. Not patching.")
        data[off:off + len(after)] = after
    if sha(data) != PATCHED_SHA256:
        sys.exit("Result hash mismatch. Not writing.")
    open(sys.argv[2], "wb").write(data)
    print(f"Wrote {sys.argv[2]}  sha256 {PATCHED_SHA256}")


if __name__ == "__main__":
    main()
