# Step-by-step guide

Placeholders used below: `PRINTER_IP` is your printer's address and `SUDO_USER` is
an SSH account on the printer that can use `sudo`. On the Q2 we used, the default
`qidi` login could **not** use sudo ("not in the sudoers file") while a second built-in
account (`mks`) could. Check yours in step 2. Change default passwords afterwards.

**Compatibility:** this guide only applies to a toolhead running THR 02.02.01.08, application
SHA-256 `1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62`. On Q2 v1.1.1
(`KLP_MCU_THR_V2_1.0.5`) use [GUIDE_V111.md](GUIDE_V111.md) instead. Step 5
checks this on your own printer before anything is changed.

Do one step at a time and check each result before the next. Stop at the first thing
that does not match.

## 1. Confirm you have the bug

Printer idle, not moving. In the Fluidd console:

```
ACCELEROMETER_MEASURE CHIP=lis2dw
```

Wait about 3 seconds and run the same command again to stop the capture. Then, on the
printer:

```
ls -t /tmp/lis2dw-*.csv | head -1
python3 check_accel_rate.py /tmp/lis2dw-YYYYMMDD_HHMMSS.csv
```

(`check_accel_rate.py` is in [tools/](../tools/).) About 390 Hz means you have the bug.
About 1600 Hz means you are already fine; stop here.

Find your chip name with `grep -n "accel_chip\|^\[lis2dw" ~/printer_data/config/printer.cfg`.

## 2. Find an account that can use sudo

On the printer, as each SSH account you have:

```
ssh -t USER@PRINTER_IP 'sudo -v && echo SUDO_OK'
```

You need `SUDO_OK`. Use `-t`, otherwise sudo cannot ask for a password.
Moonraker's service allow-list does not include `klipper` or `qidi-client`, so you
cannot stop them from Fluidd.

## 3. Get the flashing tool at a pinned commit

On your computer:

```
git clone https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized.git
cd Qidi-Max-4-Optimized
git checkout ffb302997910b0a02ac8a18b6e23274109d208f2
sha256sum scripts/flash_thr_firmware.py scripts/thr_bootloaders.py firmware/max4-thr-lis2dw-fifo-v1.json
```

Expected:

```
b68e3032bd22cb441f01648ec20dcfc8fe58cd822f9ae7cb81cca5679d9c6f0b  scripts/flash_thr_firmware.py
1169da4cc843d6bf67fa0d11ed8a46d4b0d7f69095ea8d46f007141ab0923918  scripts/thr_bootloaders.py
8619820de91730a37be0e67dd66d38b2671c01b1b7508a032c5ec11f417cd5e1  firmware/max4-thr-lis2dw-fifo-v1.json
```

Keep this exact layout and copy it to the printer as `~/q2_thr_tools`:

```
q2_thr_tools/scripts/flash_thr_firmware.py
q2_thr_tools/scripts/thr_bootloaders.py
q2_thr_tools/firmware/max4-thr-lis2dw-fifo-v1.json
```

For example, from the cloned folder: `scp -r scripts firmware USER@PRINTER_IP:q2_thr_tools/`
(after `ssh USER@PRINTER_IP mkdir -p q2_thr_tools`). Also copy `LICENSE` if you keep the files.
Run `python3 scripts/flash_thr_firmware.py --help` through sudo to check it starts.
Use Klipper's own Python for real runs: `/home/qidi/klippy-env/bin/python`.

## 4. Stop the services that own the toolhead serial port

The touchscreen and Klipper go dark. Make sure no print is running and all heaters are off.

```
ssh -t SUDO_USER@PRINTER_IP 'sudo systemctl stop tltg-optimized-auto-update.timer 2>/dev/null; sudo systemctl stop qidi-client.service && sudo systemctl stop klipper.service; systemctl is-active klipper.service qidi-client.service'
```

Expected last lines: `inactive` and `inactive`. To undo at any point:

```
ssh -t SUDO_USER@PRINTER_IP 'sudo systemctl start klipper.service; sleep 5; sudo systemctl start qidi-client.service'
```

## 5. Read-only snapshot (backs up your stock firmware and bootloader)

```
ssh -t SUDO_USER@PRINTER_IP 'cd /home/qidi/q2_thr_tools && sudo /home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py snapshot --output-dir dist/thr-before --printer-idle-confirmed; echo EXIT_CODE=$?; sudo chown -R qidi:qidi dist'
```

This only reads. Expected: `EXIT_CODE=0` and

- `application_sha256`: `1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62` (stock THR 02.02.01.08)
- `bootloader_sha256`: one of the two the tool admits. The Q2 tested here reported
  `31f8344db7b091df5429960bc9cd06065e2188c3b8092e43fb65eb3f2833723c`.

If the exit code is 3 (unrecognised bootloader) or the application hash differs, **stop**,
restart services (step 4's undo command) and open an issue with `report.json`.

## 6. Copy the backup off the printer

On your computer:

```
scp -r qidi@PRINTER_IP:q2_thr_tools/dist/thr-before ./q2-thr-before
```

Keep it. It contains your stock application and the bootloader.

## 7. Probe (reboots the toolhead, erases nothing)

```
ssh -t SUDO_USER@PRINTER_IP 'cd /home/qidi/q2_thr_tools && sudo /home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py probe --backup-dir dist/thr-before --reset --printer-idle-confirmed; echo EXIT_CODE=$?'
```

Expected: `"bootloader_reply": "0102"`, `"erase_requested": false`, `EXIT_CODE=0`. Wait 15 seconds,
then snapshot again into `dist/thr-after` (step 5 with a different `--output-dir`) and check that
the application and bootloader hashes did not change:

```
cd ~/q2_thr_tools/dist && sha256sum thr-before/application.bin thr-after/application.bin thr-before/bootloader.bin thr-after/bootloader.bin
```

## 8. Make the patched image from your own stock image

On your computer, using the application you read off your toolhead in step 6:

```
python3 tools/apply_patch.py q2-thr-before/application.bin QD_Q2_THR_02.02.01.08_20260303_FIFO_v1.bin
```

It only proceeds if the input is exactly the stock image and the output is exactly the image
the flashing tool admits (`9d2360ba47ebd720dbef07a0a4ebaf26004360bca090997d7b4a118c41460ac9`).
Copy it to the printer:

```
scp QD_Q2_THR_02.02.01.08_20260303_FIFO_v1.bin qidi@PRINTER_IP:q2_thr_tools/dist/
ssh qidi@PRINTER_IP sha256sum q2_thr_tools/dist/QD_Q2_THR_02.02.01.08_20260303_FIFO_v1.bin
```

## 9. Write it (the only step that changes the toolhead)

Stable power, you at the printer, nothing touching the power, SSH window open until the end.

```
ssh -t SUDO_USER@PRINTER_IP 'cd /home/qidi/q2_thr_tools && sudo /home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py transfer --image dist/QD_Q2_THR_02.02.01.08_20260303_FIFO_v1.bin --backup-dir dist/thr-before --reset --recover-to-stock --printer-idle-confirmed --confirm-write; echo EXIT_CODE=$?'
```

`--recover-to-stock` is for the `31f8344d...` bootloader; the tool refuses it for the other one.

- `EXIT_CODE=0`: the new image was acknowledged.
- `EXIT_CODE=4`: the write failed and the tool restored stock. Nothing changed.
- `1` or `5`: do not retry and do not restart anything. Keep the services stopped and get help.

## 10. Read it back and verify

```
ssh -t SUDO_USER@PRINTER_IP 'cd /home/qidi/q2_thr_tools && sleep 15 && sudo /home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py snapshot --output-dir dist/thr-after2 --printer-idle-confirmed; echo SNAP_EXIT=$?; sudo chown -R qidi:qidi dist; sudo /home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py verify --image dist/QD_Q2_THR_02.02.01.08_20260303_FIFO_v1.bin --backup-dir dist/thr-after2 --original-backup-dir dist/thr-before; echo VERIFY_EXIT=$?'
```

Expected: `"verified": true`, the patched application hash, the same bootloader hash as before, `VERIFY_EXIT=0`.

## 11. Bring the printer back

```
ssh -t SUDO_USER@PRINTER_IP 'sudo systemctl start klipper.service; sleep 5; sudo systemctl start qidi-client.service; systemctl is-active klipper.service qidi-client.service'
```

Check Fluidd shows Ready with no errors. The fix persists across reboots.

## 12. Measure again

Repeat step 1. You should see about 1600 Hz and a max gap near 1 ms. Then rerun
`SHAPER_CALIBRATE`, since any earlier input shaper values came from the broken rate.

## Going back to stock

The same tool admits the stock image. With services stopped as in step 4:

```
ssh -t SUDO_USER@PRINTER_IP 'cd /home/qidi/q2_thr_tools && sudo /home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py transfer --image dist/thr-before/application.bin --backup-dir dist/thr-before --reset --recover-to-stock --printer-idle-confirmed --confirm-write; echo EXIT_CODE=$?'
```

Then snapshot and verify as in step 10 (with `--image dist/thr-before/application.bin`).
Qidi's own updater (`/home/qidi/mcu_update_THR.sh` and the official update package)
is an independent way to put stock back if the toolhead does not respond.

## Notes

- A Qidi firmware update that includes a toolhead update will overwrite the patch. Check the rate again afterwards.
- Run the real steps only with the services stopped; the tool refuses otherwise.
