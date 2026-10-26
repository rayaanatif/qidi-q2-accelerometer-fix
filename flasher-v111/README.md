# EXPERIMENTAL flasher for Qidi Q2 v1.1.1 (THR KLP_MCU_THR_V2_1.0.5)

**Not hardware-tested. Use only if you accept that the toolhead could end up needing recovery.**

A minimal fork of the Qidi-Max-4-Optimized flasher (commit `ffb30299`, GPL-3.0) that admits only:

| | size | sha256 |
|---|---|---|
| stock v1.1.1 THR | 34,780 | `e114de22c629167381b68eb6e477b2a8dc93ee98fb2fbdb3c828f95a224c8f8b` |
| patched (made by `tools/lis2dw_patch.py`) | 34,780 | `3927036f418976aa34c61f09ad426364e23df1b04687678424df7c6593eccfae` |

and only the bootloaders the original tool already knows (`31f8344d…` is the one seen on a v1.1.1 printer and has recover-to-stock). Everything else is unchanged; see `CHANGES.diff` (manifest file name, and Klipper's path is searched instead of hardcoded to `/home/qidi`).

Differences from the Q2 02.02.01.08 guide on a v1.1.1 printer: the user is `mks`, Klipper is `/home/mks/klipper`, there is no `qidi-client.service`, so stop only `klipper.service`.

`python3 selftest.py STOCK PATCHED BOOTLOADER OTHER` checks the admission logic offline (what is accepted and refused). It does not test the serial transfer, which is the unchanged upstream code.

The read-only snapshot with this tool reads exactly 34,780 bytes, so a fresh snapshot hashes to the stock value (the original tool read 35,056 bytes, which included padding).
