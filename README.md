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

## Tested so far (two printers)

| Printer firmware | Toolhead image (SHA-256 prefix) | Rate before | Rate after | Flasher | Guide |
|---|---|---|---|---|---|
| 01.01.02.04 (NA) | THR 02.02.01.08 (`1d34b4b0`) | 387 Hz | 1606 Hz | upstream tool | [GUIDE.md](docs/GUIDE.md) |
| v1.1.1 | THR KLP_MCU_THR_V2_1.0.5 (`e114de22`) | 386 Hz | 1602 Hz | [flasher-v111](flasher-v111/) (experimental) | [GUIDE_V111.md](docs/GUIDE_V111.md) |

Both toolhead bootloaders were `31f8344d...`. Largest gap between samples after the fix: 0.6 ms.
One printer per image is a small sample. If you try it, please open an issue with your versions and
the output of the `snapshot` step.

## Which guide do I follow?

1. Find out which toolhead image you have. In the klippy log, `grep "Loaded MCU 'THR'" ~/printer_data/logs/klippy.log`:
   `KLP_MCU_THR_V2_1.0.5` is the v1.1.1 image. Anything else, do not guess.
2. The authority is the SHA-256 of the application read off your toolhead (the read-only snapshot step in either guide).
   - `1d34b4b0...` -> [docs/GUIDE.md](docs/GUIDE.md)
   - `e114de22...` -> [docs/GUIDE_V111.md](docs/GUIDE_V111.md) (experimental)
   - anything else -> stop. Run `python3 tools/lis2dw_patch.py fingerprint <your image>` and open an issue with the output; nothing here has been checked on it.
3. Windows and macOS tips: Git for Windows converts line endings and changes file hashes, so clone with
   `git clone -c core.autocrlf=false ...`. PowerShell does not accept `&&` in the commands that run on the printer; run those in an SSH session
   on the printer. On macOS (zsh), quote remote wildcards: `scp "user@host:path/*.ext" .`.

## Compatibility: one exact toolhead image only

The patch changes bytes inside the toolhead (THR) firmware, so it only works on that exact image:

- **Works on:** Qidi Q2 toolhead firmware **THR 02.02.01.08** (35,056 bytes, SHA-256
  `1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62`). That image ships inside
  printer firmware **01.01.02.04 (NA)**. Other Q2 releases may carry the same image; check
  yours, do not assume.
- **Also tested, experimental:** the toolhead image in Qidi's `Q2_V1_1_1` package (34,780 bytes, SHA-256
  `e114de22c629167381b68eb6e477b2a8dc93ee98fb2fbdb3c828f95a224c8f8b`). It has the same bug compiled
  differently from the Max 4 image; `tools/lis2dw_patch.py` and the fork in
  [flasher-v111/](flasher-v111/) handle it. Flashed and measured on one printer (386 -> 1602 Hz). See
  [docs/OLDER_FIRMWARE.md](docs/OLDER_FIRMWARE.md) and [docs/GUIDE_V111.md](docs/GUIDE_V111.md).
- **Anything else:** not supported. `lis2dw_patch.py scan` / `fingerprint` tell you whether an image has a site it
  recognises, but a match is not a hardware test.
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

Pick your guide in "Which guide do I follow?" above. Helper scripts live in [tools/](tools/):
`check_accel_rate.py` (measure the rate) and `lis2dw_patch.py` (scan / fingerprint / patch for both known images;
it refuses unknown or already patched images).

## Credits

- The patch sites and the flashing tool: [thelegendtubaguy/Qidi-Max-4-Optimized](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized) (GPL-3.0). [GUIDE.md](docs/GUIDE.md) fetches it at a pinned commit; [flasher-v111/](flasher-v111/) is a small modified copy of it (GPL-3.0, changes in `CHANGES.diff`).
- The upstream Klipper fix: commit 6269dda by the Klipper developers.

License: GPL-3.0, to match the upstream project the patch information comes from.
