# Older toolhead firmware (experimental, untested on hardware)

**Status: nobody has flashed the older-image patch described here. Do not use it on a printer
unless you accept the risk of a dead toolhead and know how to recover it.**

## What was found

Qidi's `Q2_V1_1_1` package contains an older toolhead image (34,780 bytes). Its built-in
identifier reads `KLP_MCU_THR_V2_1.0.5` and it reports 124 commands, while the tested image
(THR 02.02.01.08) reports 127. The file contains the same polling routine with the same
branch inversion, compiled with 16-bit Thumb instructions instead of 32-bit ones:

```
stock                      patched
cbnz r6, +14               cbz  r6, +14        ; run again only when samples remain
ldr  r3, [pc, #76]
strb r6, [r3, #8]          strb r7, [r3, #8]   ; store zero (r7 is zero throughout)
movs r2, #1
```

`r7` is set by `movs r7,#0` in the function prologue and is only ever read afterwards, so
`strb r7` stores zero. Two single-bit edits (file offsets `0x4395` and `0x4398`) give a patched
image with SHA-256 `3927036f418976aa34c61f09ad426364e23df1b04687678424df7c6593eccfae`.
Stock image SHA-256: `e114de22c629167381b68eb6e477b2a8dc93ee98fb2fbdb3c828f95a224c8f8b`.

## The tool

```
python3 tools/lis2dw_patch.py scan  your-thr-image.bin
python3 tools/lis2dw_patch.py patch your-thr-image.bin patched.bin
```

It matches instruction templates with wildcards for the values that move between builds, so
it may also recognise a future Qidi image that was built the same way. It requires exactly one
match, refuses images already patched, and refuses unknown images unless `--allow-unknown`
is given. A match only proves the code looks the same, not that it is safe to flash.

## What stops this being "universal"

- **Different compilers or code layout** change the instructions and the templates will not match.
  A new template needs to be derived and checked by reading the disassembly.
- **The `r7`-is-zero assumption** (older template) was checked by hand for the one image above only.
- **The upstream flashing tool refuses unknown images.** It only admits the exact stock and patched
  hashes it was built for, and the old patched image is not one of them. Making it accept new
  images means forking that tool and taking responsibility for the change, or using another
  flashing route. This repo does not do either.
- **The toolhead bootloader** of an older printer has not been inspected. The tool checks the
  bootloader hash against two known values, and an older unit may differ.

## Other images: how to get a template made

```
python3 tools/lis2dw_patch.py fingerprint your-thr-image.bin
```

It prints the size, SHA-256, the version name embedded in the image, any template match, and, if
the FIFO routine is present but compiled differently, a hex dump around it. Post that output in an
issue. A template is only added after the surrounding code has been read and the edit checked.

Example of why this is needed: the main-board image in the same `Q2_V1_1_1` package
(`KLP_MCU_MAIN_V2_1.0.4`) contains the same routine in a third form (16-bit branch, 32-bit store),
so neither existing template matches it. That image is not the one with the accelerometer on a Q2,
so nothing is patched there, but it shows that a new build can need a new template.

## If you want to test it

1. Run the read-only `snapshot` step of [GUIDE.md](GUIDE.md) on a printer with this toolhead image
   and compare the application hash with `e114de22...` above. Post the result.
2. Only after a hardware owner has verified a flash and the sample rate afterwards (about 1600 Hz
   with the helper script), should it be marked tested in `KNOWN` inside `lis2dw_patch.py`.

The practical alternative for most people: update the printer through Qidi's online update, which
brings the toolhead to 02.02.01.08, and follow the main guide.

## Register-agnostic matching (update)

`tools/lis2dw_patch.py` no longer hard-codes which registers the compiler picked. It matches the
instruction *shape* of the two known builds (32-bit form from THR 02.02.01.08, 16-bit form from
the v1.1.1 THR) with any registers, then derives the edit from what it finds: the scratch register
for the zero store (template B) or a register proven to hold zero since the function prologue
(template A, conservative scan that refuses if anything could have overwritten it). It still
requires exactly one match and refuses otherwise.

This is built from only those two images. That other Q2 releases are structured the same is an
**assumption**; run `scan` / `fingerprint` on any new image first. Only 02.02.01.08 is verified
on hardware. Everything else prints an UNTESTED warning, and flashing still needs a route that
accepts the image (the upstream flasher only admits pinned hashes).
