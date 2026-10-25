#!/usr/bin/env python3
"""Report the real sample rate of a Klipper accelerometer capture CSV.

Usage:  python3 check_accel_rate.py /tmp/lis2dw-YYYYMMDD_HHMMSS.csv

Capture one first, with the printer idle and not moving, in the Fluidd console:
    ACCELEROMETER_MEASURE CHIP=lis2dw      (wait ~3 s, then run it again to stop)
A healthy LIS2DW configured for 1600 Hz reports ~1600 Hz and a max gap of ~1 ms.
The bug reports ~390 Hz.
"""
import sys

if len(sys.argv) != 2:
    sys.exit(__doc__)

t = []
with open(sys.argv[1]) as f:
    for line in f:
        if line.startswith("#") or not line.strip():
            continue
        try:
            t.append(float(line.split(",")[0]))
        except ValueError:
            continue

if len(t) < 100:
    sys.exit("Not enough samples in file.")

dur = t[-1] - t[0]
rate = (len(t) - 1) / dur
gap = max(b - a for a, b in zip(t, t[1:])) * 1000
verdict = "OK" if rate > 1400 else "BAD (sample-rate bug present)"
print(f"samples {len(t)}  duration {dur:.2f}s  rate {rate:.0f} Hz  max gap {gap:.1f} ms  -> {verdict}")
