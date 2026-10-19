#!/usr/bin/env python3
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='nomifun-keys-') as output:
    common = ['cc', '-D_GNU_SOURCE', '-std=c11', '-Wall', '-Wextra', '-Werror']
    include = sum((['-I', str(ROOT / p)] for p in ['tests/native/include', 'components/vk_usb/include', 'components/vk_input/include', 'components/nk_screen/include']), [])
    for name, files in {
        'test_native_control': ['components/vk_usb/vk_usb_json.c', 'components/vk_input/vk_input_debounce.c', 'components/nk_screen/nk_screen_render.c'],
        'test_vk_usb_json': ['components/vk_usb/vk_usb_json.c'],
        'test_input_debounce': ['components/vk_input/vk_input_debounce.c'],
        'test_screen_panel': ['components/nk_screen/nk_screen_render.c'],
        'test_screen_render': ['components/nk_screen/nk_screen_render.c'],
    }.items():
        binary = Path(output) / name
        subprocess.run(common + include + [str(ROOT / ('tests/native/' + name + '.c'))] + [str(ROOT / p) for p in files] + ['-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        if name == 'test_screen_panel':
            subprocess.run([str(binary), 'fail'], check=True)
        if name == 'test_screen_render' and len(__import__('sys').argv) > 1:
            destination = Path(__import__('sys').argv[1]).resolve()
            destination.mkdir(parents=True, exist_ok=True)
            subprocess.run([str(binary), str(destination)], check=True)
    print('All five key/screen native test programs and driver failure scenario passed.')
