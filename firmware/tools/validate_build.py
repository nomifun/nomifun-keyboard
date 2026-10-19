#!/usr/bin/env python3
"""Validate the native firmware image without opening or writing any device."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'build-native-screen')
app = BUILD / 'vibe_keyboard.bin'
elf = BUILD / 'vibe_keyboard.elf'
config = (BUILD / 'config/sdkconfig.h').read_text(encoding='utf-8')
for key in ['CONFIG_IDF_TARGET "esp32s3"', 'CONFIG_ESPTOOLPY_FLASHSIZE_16MB 1', 'CONFIG_ESP_CONSOLE_NONE 1', 'CONFIG_ESP_CONSOLE_SECONDARY_NONE 1', 'CONFIG_LOG_DEFAULT_LEVEL_NONE 1', 'CONFIG_BOOTLOADER_LOG_LEVEL_NONE 1', 'CONFIG_ESP_SYSTEM_PANIC_SILENT_REBOOT 1']:
    if '#define ' + key not in config:
        raise SystemExit('Missing production configuration: ' + key)
if not 0 < app.stat().st_size <= 0x500000:
    raise SystemExit('Application does not fit actual OTA slot')
image = subprocess.run([sys.executable, '-m', 'esptool', '--chip', 'esp32s3', 'image_info', '--version', '2', str(app)], check=True, capture_output=True, text=True).stdout
if 'checksum:' not in image.lower() or '(valid)' not in image or 'validation hash:' not in image.lower():
    raise SystemExit('Invalid application image checksum/hash')
if not re.search(r'App version:\s+0\.3-screen\.2\b', image):
    raise SystemExit('Application descriptor does not match current source version 0.3-screen.2')
names = {line.split()[-1] for line in subprocess.run([os.environ.get('NM', 'xtensa-esp32s3-elf-nm'), '-g', str(elf)], check=True, capture_output=True, text=True).stdout.splitlines() if line.split()}
for prefix in ['esp_wifi_', 'esp_bt_', 'esp_ble_', 'tinyusb_', 'tud_', 'vk_asset_', 'vk_screen_', 'vk_update_', 'vk_led_', 'vk_audio_', 'opus_', 'i2s_channel_', 'esp_afe_']:
    if any(name.startswith(prefix) for name in names):
        raise SystemExit('Unexpected linked feature: ' + prefix)
partition = (ROOT / 'partitions.csv').read_text(encoding='utf-8')
rows = [line.split(',') for line in partition.splitlines() if line.strip() and not line.startswith('#')]
app_row = next((row for row in rows if row[0].strip() == 'ota_0'), None)
if app_row is None or int(app_row[3].strip(), 0) != 0x20000 or int(app_row[4].strip(), 0) != 0x500000:
    raise SystemExit('Partition source does not preserve actual app layout')
print(json.dumps({'protocol': 1, 'firmware': '0.3-screen.2', 'app_bytes': app.stat().st_size, 'sha256': hashlib.sha256(app.read_bytes()).hexdigest(), 'image_checksum': 'valid', 'device_written': False}, indent=2))



