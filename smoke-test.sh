#!/usr/bin/env bash
set -euo pipefail
if (($# != 2)); then
    printf 'Usage: bash smoke-test.sh IMAGE /path/to/affected.mp4\n' >&2
    exit 2
fi
image="$1"
sample="$2"
[[ -f "$sample" && -r "$sample" ]] || { printf 'Sample must be a readable file\n' >&2; exit 2; }
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
sample_dir="$(cd -- "$(dirname -- "$sample")" && pwd -P)"
filename="$(basename -- "$sample")"
# Expose only the chosen file, under a generic name, rather than its directory.
docker run --rm -i --network none --entrypoint node \
    --mount "type=bind,src=$sample_dir/$filename,dst=/external/photos/sample.mp4,readonly" \
    --mount "type=bind,src=$script_dir/ffmpeg-motion-photo-wrapper,dst=/usr/local/bin/ffmpeg-motion-photo-wrapper,readonly" \
    --tmpfs /data/thumbs:rw,size=33554432 \
    -e FFMPEG_PATH=/usr/local/bin/ffmpeg-motion-photo-wrapper \
    "$image" - < "$script_dir/native-thumbnail.cjs"
