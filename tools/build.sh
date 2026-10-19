#!/usr/bin/env bash
# ESP-IDF build + offline image validation for the four-key firmware.
# Requires ESP-IDF 5.5.x; set IDF_PATH or source export.sh beforehand.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-build-native-screen}"

if [ -z "${IDF_PATH:-}" ]; then
    for candidate in "$HOME"/.espressif/frameworks/esp-idf-v5.5.*; do
        [ -d "$candidate" ] && IDF_PATH="$candidate"
    done
fi
if [ -z "${IDF_PATH:-}" ] || [ ! -f "$IDF_PATH/export.sh" ]; then
    echo "ESP-IDF 5.5.x not found. Export IDF_PATH to its installation directory." >&2
    exit 1
fi

# shellcheck disable=SC1091
. "$IDF_PATH/export.sh" >/dev/null

cd "$ROOT/firmware"
python "$IDF_PATH/tools/idf.py" -B "$BUILD_DIR" -DIDF_TARGET=esp32s3 build
python tools/validate_build.py "$BUILD_DIR"
