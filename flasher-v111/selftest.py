#!/usr/bin/env python3
"""Offline checks of the admission logic (no hardware). Usage: selftest.py STOCK PATCHED BOOTLOADER OTHER_Q2_IMAGE"""
import json, sys, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "scripts"))
import flash_thr_firmware as f
m = json.loads(f.MANIFEST.read_text())
stock, patched, boot, other = (pathlib.Path(a).read_bytes() for a in sys.argv[1:5])
def refuses(fn, *a):
    try: fn(*a)
    except ValueError: return True
    return False
assert f.admitted_image(stock, m) == m["thr"]["stock_sha256"]
assert f.admitted_image(patched, m) == m["thr"]["patched_sha256"]
assert refuses(f.admitted_image, other, m), "02.02.01.08 image must be refused"
assert refuses(f.admitted_image, stock + b"\xff" * 276, m), "padded image must be refused"
assert refuses(f.admitted_image, stock[:-4] + b"\0\0\0\0", m), "modified image must be refused"
assert f.identify_bootloader(boot).recoverable
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "bootloader.bin").write_bytes(boot); (d / "application.bin").write_bytes(stock)
    b, a = f.load_backup(d, m); assert a == stock
    (d / "application.bin").write_bytes(patched)
    assert f.verify_readback(patched, d, m, expected_bootloader=boot)["verified"]
    assert refuses(f.verify_readback, patched, d, m, ) is False
    (d / "application.bin").write_bytes(stock)
    assert refuses(f.verify_readback, patched, d, m), "stock readback must not verify as patched"
    (d / "bootloader.bin").write_bytes(boot[:-1] + b"\x00")
    assert refuses(f.load_backup, d, m), "wrong bootloader must be refused"
print("selftest OK")
