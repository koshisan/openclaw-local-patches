#!/usr/bin/env bash
# Apply all patches under patches/ in deterministic order.
# Forwards --dry-run and --openclaw <path> to each patch script.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHES_DIR="$HERE/patches"

if [[ ! -d "$PATCHES_DIR" ]]; then
    echo "no patches/ directory next to $0" >&2
    exit 2
fi

shopt -s nullglob
mapfile -t SCRIPTS < <(printf '%s\n' "$PATCHES_DIR"/*.py | sort)

if (( ${#SCRIPTS[@]} == 0 )); then
    echo "no patches to apply."
    exit 0
fi

echo "will run ${#SCRIPTS[@]} patch script(s):"
for s in "${SCRIPTS[@]}"; do echo "  - ${s##*/}"; done
echo

failed=0
for script in "${SCRIPTS[@]}"; do
    echo "=== ${script##*/} ==="
    if ! python3 "$script" "$@"; then
        failed=$((failed + 1))
        echo "[FAIL] ${script##*/} returned non-zero"
    fi
    echo
done

if (( failed > 0 )); then
    echo "$failed patch(es) failed." >&2
    exit 1
fi

echo "all patches applied."
