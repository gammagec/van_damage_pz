#!/usr/bin/env bash
# Creates lowercase symlinks for mod folders whose names contain uppercase
# letters, so that Windows-authored mods whose scripts reference lowercase
# paths work on Linux without any file editing.
#
# Safe to rerun -- symlinks that already exist are silently skipped.
# Only touches mods/ subdirectories inside each Workshop item; never touches
# other content or save data.
#
# Usage: scripts/fix-mod-case.sh <testing|prod>
set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "testing" && "$ENV" != "prod" ]]; then
    echo "Usage: $0 <testing|prod>" >&2
    exit 1
fi

VOLUME="pz_${ENV}_data"
MSYS_NO_PATHCONV=1

SCRIPT=$(cat <<'INNER'
set -e

CONTENT_BASE="/dest/pzserver/steamapps/workshop/content/108600"

if [ ! -d "$CONTENT_BASE" ]; then
    echo "No workshop content at $CONTENT_BASE -- deploy the server first." >&2
    exit 0
fi

fixed=0
skipped=0

for item_dir in "$CONTENT_BASE"/*/; do
    [ -d "$item_dir" ] || continue
    mods_dir="${item_dir}mods"
    [ -d "$mods_dir" ] || continue

    for mod_dir in "$mods_dir"/*/; do
        [ -d "$mod_dir" ] || continue
        folder=$(basename "$mod_dir")
        lower=$(echo "$folder" | tr '[:upper:]' '[:lower:]')

        # Already all lowercase -- nothing to do.
        if [ "$folder" = "$lower" ]; then
            continue
        fi

        symlink="${mods_dir}/${lower}"

        if [ -e "$symlink" ] || [ -L "$symlink" ]; then
            skipped=$((skipped + 1))
            continue
        fi

        echo "  ${mods_dir#/dest/}/${lower} -> ${folder}"
        ln -s "$folder" "$symlink"
        fixed=$((fixed + 1))
    done
done

echo ""
echo "Created ${fixed} symlink(s), skipped ${skipped} already-existing."
INNER
)

echo "Fixing mod case in volume: $VOLUME"
echo ""

docker run --rm \
    -v "${VOLUME}:/dest" \
    alpine \
    sh -c "$SCRIPT"
