# Qidi Q2: fix the accelerometer sample rate (LIS2DW)

On the Qidi Q2 the toolhead accelerometer (LIS2DW) is configured for 1600 Hz but
actually delivers about **390 Hz**, because of a bug in the toolhead (THR) firmware
that was fixed upstream in Klipper
([commit 6269dda](https://github.com/Klipper3d/klipper/commit/6269dda56bb7c08263153b18715d08e2d964bcab)).
Input shaper results measured at the wrong rate are unreliable. There is no
host-side fix: the toolhead firmware has to be reflashed.

This repo is a step-by-step record of doing that on a Q2, using the flashing tool and
two-byte-site patch from the Qidi Max 4 community project. It contains **no Qidi
firmware**; you read the image off your own toolhead and patch it locally.

| | Before | After |
|---|---|---|
| Accelerometer rate | 387 Hz | 1606 Hz |
| Largest gap between samples | irregular | 0.6 ms |

**Tested on exactly one printer:** Q2, printer firmware 01.01.02.04, main MCU
02.01.01.09, toolhead (THR) 02.02.01.08, toolhead bootloader hash `31f8344d...`.
Nobody else has reported a Q2 result yet. If you try it, please open an issue with
your versions and the output of the `snapshot` step.

## Compatibility: one exact toolhead image only

The patch changes bytes inside the toolhead (THR) firmware, so it only works on that exact image:

- **Works on:** Qidi Q2 toolhead firmware **THR 02.02.01.08** (35,056 bytes, SHA-256
  `1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62`). That image ships inside
  printer firmware **01.01.02.04 (NA)**. Other Q2 releases may carry the same image; check
  yours, do not assume.
- **Does not work on:** older toolhead images. For example the toolhead file in Qidi's
  `Q2_V1_1_1` package (34,780 bytes, SHA-256
  `e114de22c629167381b68eb6e477b2a8dc93ee98fb2fbdb3c828f95a224c8f8b`) contains neither of the two
  byte patterns the patch looks for, so the tools refuse it. The same bug is present in its code, and
  a derived patch has been flashed and measured on one printer (386 Hz -> 1602 Hz); it needs the experimental flasher in
  [flasher-v111/](flasher-v111/). One printer only, so treat it as experimental; see
  [docs/OLDER_FIRMWARE.md](docs/OLDER_FIRMWARE.md).
- **The printer software version alone does not decide it.** What matters is the SHA-256 of the
  application running on your toolhead. Step 5 of the guide reads it with a read-only snapshot.
  If it is not the hash above, stop; nothing in this repo applies to your toolhead.
- **A Qidi update that includes a new toolhead image overwrites the fix** and the patch would
  have to be redone for that new image.

## Read this first

- **This reflashes your toolhead.** A power cut or crash during the write can leave it
  without a working application until you recover it. The bootloader is never
  touched, so recovery should be possible, but that is not guaranteed.
- It may affect support from Qidi for the toolhead firmware. Putting the stock image
  back is documented in the guide.
- I am not affiliated with Qidi, Klipper, or the authors of the upstream tool.
  Everything here is at your own risk.

## Start

Follow [docs/GUIDE.md](docs/GUIDE.md). Helper scripts live in [tools/](tools/). For other toolhead images see [docs/OLDER_FIRMWARE.md](docs/OLDER_FIRMWARE.md) (experimental, untested).

## Credits

- The patch sites and the flashing tool: [thelegendtubaguy/Qidi-Max-4-Optimized](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized) (GPL-3.0). This repo does not copy its code; the guide tells you how to fetch it at a pinned commit.
- The upstream Klipper fix: commit 6269dda by the Klipper developers.

License: GPL-3.0, to match the upstream project the patch information comes from.
