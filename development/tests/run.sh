#!/usr/bin/env bash
set -euo pipefail
package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build=$(mktemp -d /tmp/borealis-test.XXXXXX)
trap 'rm -f -- "$build/performance_test"; rmdir -- "$build"' EXIT
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined \
 "$package/project/vendor/borealis/performance/engine.cpp" "$package/tests/performance_test.cpp" -o "$build/performance_test"
"$build/performance_test"
python3 -m py_compile "$package"/tools/*.py
