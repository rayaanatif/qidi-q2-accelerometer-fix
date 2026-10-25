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

## Read this first

- **This reflashes your toolhead.** A power cut or crash during the write can leave it
  without a working application until you recover it. The bootloader is never
  touched, so recovery should be possible, but that is not guaranteed.
- It may affect support from Qidi for the toolhead firmware. Putting the stock image
  back is documented in the guide.
- I am not affiliated with Qidi, Klipper, or the authors of the upstream tool.
  Everything here is at your own risk.

## Start

Follow [docs/GUIDE.md](docs/GUIDE.md). Helper scripts live in [tools/](tools/).

## Credits

- The patch sites and the flashing tool: [thelegendtubaguy/Qidi-Max-4-Optimized](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized) (GPL-3.0). This repo does not copy its code; the guide tells you how to fetch it at a pinned commit.
- The upstream Klipper fix: commit 6269dda by the Klipper developers.

License: GPL-3.0, to match the upstream project the patch information comes from.
