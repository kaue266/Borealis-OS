#!/usr/bin/env bash
set -euo pipefail
package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -f "$scratch/frame-clock"; rmdir "$scratch"' EXIT
c++ -std=c++17 -Wall -Werror -fsanitize=address,undefined \
 -I"$package/project/frameworks/native/libs/renderengine/skia" \
 "$package/tests/frame_clock_test.cpp" -o "$scratch/frame-clock"
"$scratch/frame-clock"
"${BOREALIS_GRAPHICS_PYTHON:-python3}" "$package/tests/graphics_test.py" --project "$package/project"
