# Guide: Qidi Q2 on v1.1.1 (toolhead KLP_MCU_THR_V2_1.0.5) — EXPERIMENTAL

Tested end to end on **one** printer (386 Hz -> 1602 Hz). Read [OLDER_FIRMWARE.md](OLDER_FIRMWARE.md) first.
This is **not** the guide for toolhead 02.02.01.08; that is [GUIDE.md](GUIDE.md).

Differences on a v1.1.1 printer (check yours, do not assume): the SSH user is `mks`, Klipper is in
`/home/mks/klipper` with its Python in `/home/mks/klippy-env`, there is no `qidi` user and no
`qidi-client.service`, so only `klipper.service` is stopped. The group of `mks` was `netdev`.
Commands marked **(printer)** run in an SSH session on the printer (for example MobaXterm);
**(PC)** runs on your computer (PowerShell is fine). Replace `PRINTER_IP`. Do one step at a time and
stop at the first result that does not match.

## 1. Confirm you have the bug and the right toolhead (printer)
In the Fluidd console run `ACCELEROMETER_MEASURE CHIP=lis2dw` (chip name from
`grep -n "accel_chip\|^\[lis2dw" ~/printer_data/config/printer.cfg`), wait 3 s, run it again, then:
```
python3 check_accel_rate.py $(ls -t /tmp/lis2dw-*.csv | head -1)
```
About 390 Hz means you have the bug. Also check the klippy log or Fluidd for `KLP_MCU_THR_V2_1.0.5`.
(`tools/check_accel_rate.py` is in this repo; `scp` it to the printer.)

## 2. Check sudo (PC)
```
ssh -t mks@PRINTER_IP "sudo -v && echo SUDO_OK"
```

## 3. Get this repo without line-ending conversion (PC)
Windows Git converts line endings and changes file hashes, so switch that off:
```
git clone -c core.autocrlf=false https://github.com/rayaanatif/qidi-q2-accelerometer-fix.git
cd qidi-q2-accelerometer-fix
```
Copy the flasher and the patcher to the printer:
```
ssh mks@PRINTER_IP "mkdir -p ~/q2fork"
scp -r flasher-v111\scripts flasher-v111\firmware flasher-v111\selftest.py tools\lis2dw_patch.py mks@PRINTER_IP:q2fork/
```
Check on the printer: `ls ~/q2fork ~/q2fork/scripts ~/q2fork/firmware`.

## 4. Read-only snapshot = your backup (printer)
Printer idle, heaters off. The touchscreen shows a Klipper error while Klipper is stopped; that is normal.
```
sudo systemctl stop klipper.service; cd ~/q2fork && sudo ~/klippy-env/bin/python scripts/flash_thr_firmware.py snapshot --output-dir /home/mks/thr-backups/thr-before --printer-idle-confirmed; echo EXIT_CODE=$?; sudo chown -R mks:netdev /home/mks/thr-backups; sudo systemctl start klipper.service; sleep 5; systemctl is-active klipper.service
```
Required: `EXIT_CODE=0`, `application_sha256` = `e114de22c629167381b68eb6e477b2a8dc93ee98fb2fbdb3c828f95a224c8f8b`,
`bootloader_sha256` = `31f8344db7b091df5429960bc9cd06065e2188c3b8092e43fb65eb3f2833723c`, final `active`.
If any hash differs, **stop**: this guide does not apply to your toolhead.

## 5. Copy the backup off the printer (PC) and keep a second copy
```
scp -r mks@PRINTER_IP:/home/mks/thr-backups/thr-before .\q2-thr-before
```

## 6. Probe (printer): resets the toolhead, erases nothing
```
sudo systemctl stop klipper.service; cd ~/q2fork && sudo ~/klippy-env/bin/python scripts/flash_thr_firmware.py probe --backup-dir /home/mks/thr-backups/thr-before --reset --printer-idle-confirmed; echo PROBE_EXIT=$?; sleep 15; sudo ~/klippy-env/bin/python scripts/flash_thr_firmware.py snapshot --output-dir /home/mks/thr-backups/thr-after --printer-idle-confirmed; echo SNAP_EXIT=$?; sudo chown -R mks:netdev /home/mks/thr-backups; cd /home/mks/thr-backups && sha256sum thr-before/application.bin thr-after/application.bin thr-before/bootloader.bin thr-after/bootloader.bin; sudo systemctl start klipper.service; sleep 5; systemctl is-active klipper.service
```
Required: `"bootloader_reply": "0102"`, `"erase_requested": false`, both exit codes 0, the two
application hashes equal and the two bootloader hashes equal. Otherwise **stop**.

## 7. Build the patched image from your own backup (printer)
```
cd ~/q2fork && mkdir -p dist && ~/klippy-env/bin/python lis2dw_patch.py patch /home/mks/thr-backups/thr-before/application.bin dist/patched.bin && sha256sum dist/patched.bin
```
Must be `3927036f418976aa34c61f09ad426364e23df1b04687678424df7c6593eccfae`.

## 8. Write it (printer) — the only step that changes the toolhead
Stable power, you at the printer, SSH window open until the end.
```
sudo systemctl stop klipper.service; cd ~/q2fork && sudo ~/klippy-env/bin/python scripts/flash_thr_firmware.py transfer --image dist/patched.bin --backup-dir /home/mks/thr-backups/thr-before --reset --recover-to-stock --printer-idle-confirmed --confirm-write; echo EXIT_CODE=$?
```
`0` = accepted. `4` = failed and stock was restored. Anything else: do not retry and do not restart
Klipper; keep the services stopped and ask for help.

## 9. Read back and verify (printer)
```
sleep 15; cd ~/q2fork && sudo ~/klippy-env/bin/python scripts/flash_thr_firmware.py snapshot --output-dir /home/mks/thr-backups/thr-after2 --printer-idle-confirmed; echo SNAP_EXIT=$?; sudo ~/klippy-env/bin/python scripts/flash_thr_firmware.py verify --image dist/patched.bin --backup-dir /home/mks/thr-backups/thr-after2 --original-backup-dir /home/mks/thr-backups/thr-before; echo VERIFY_EXIT=$?
```
Expect `"verified": true` and `VERIFY_EXIT=0`. Then `sudo systemctl start klipper.service; sleep 5; systemctl is-active klipper.service`.

## 10. Measure
Repeat step 1. About 1600 Hz means it worked. Then redo input shaper calibration.

## Undo
Same transfer command as step 8 with `--image /home/mks/thr-backups/thr-before/application.bin`, then step 9
with that image. If the toolhead application no longer answers, `--reset` cannot work; power-cycle and
run it without `--reset` within the bootloader's startup window (not tested).
