# Immich Motion Photo thumbnail wrapper

An FFmpeg wrapper that helps Immich generate previews for a specific type of Motion Photo file. This is an independent workaround that runs alongside Immich; it requires no application source changes or custom Docker image.

## ELI5

You open Immich to browse your photos, but some Motion Photos have no thumbnail. Immich has the file, but fails to create the small preview you need to see it in your library.

The thumbnail tool can choose the wrong part of the file. This wrapper points it to the right part. After installation, retrying the failed thumbnail jobs can restore normal previews for affected items.

Your original photos and videos stay unchanged.

## What does this fix in everyday use?

The visible result is a usable preview in your library for items affected by this particular failure. Installing the wrapper does not automatically repair previously failed jobs: you need to retry thumbnail generation for those items. Start with one known affected asset before processing more.

The workaround applies to thumbnail generation. It does not change motion playback or address every cause of missing previews.

## Why thumbnail generation fails

Some Motion Photo MP4 files contain two HEVC video streams:

- Stream 0 contains the moving video, with more than one frame and a positive duration.
- Stream 1 contains one frame, reports zero duration, and can have a higher resolution.

FFmpeg's automatic stream selection can favor the higher-resolution stream. Immich's thumbnail filter chain may then produce no frames and fail, including with exit code 244.

For the confirmed layout, the wrapper adds `-map 0:0` to select the actual video stream. The remaining command arguments are preserved.

## Scope and safeguards

The wrapper changes a command only when all of these conditions are satisfied:

- There is exactly one `-i` input.
- The input is a readable MP4 under `/external/photos/`.
- The final output is a WebP or JPEG file under `/data/thumbs/`.
- The command requests one output frame through `-frames:v 1` or `-vframes 1`.
- There is no existing `-map` and no recognized complex-filter option.
- A successful probe identifies exactly two HEVC video streams, with indices 0 and 1 and the frame/duration pattern described above.

Other commands are passed to the original FFmpeg unchanged. The wrapper preserves FFmpeg's exit status through `exec`.

The additional `ffprobe` call has a 15-second timeout, followed by a 2-second forced-termination grace period. A probe failure or timeout causes the original command to run unchanged; this limits the extra probe, not the subsequent FFmpeg process. The wrapper's own message does not include input filenames or paths. FFmpeg and Immich may still log their normal diagnostic information.

Different stream indices, missing metadata, other codecs, or other library mount paths are outside its tested scope.

## Requirements

Inside the Immich server container:

- Bash with associative arrays and namerefs (Bash 4.3 or later).
- `/usr/bin/ffmpeg` and `/usr/bin/ffprobe`.
- GNU-compatible `/usr/bin/timeout` with `--kill-after` support.

The library must be available inside the container at `/external/photos/`. This is a container mount path, not a prescribed host directory. If your container uses another path, review and adapt the input allowlist in the script before installation. Do not replace it with an unrestricted match without understanding the consequences.

## Installation

The following commands run on the Docker host. Replace `/path/to/immich-stack` with the directory containing your Immich Compose configuration.

```sh
git clone https://github.com/janmichalski/immich-motion-photo-wrapper.git
cd immich-motion-photo-wrapper
python3 -m unittest -v test_wrapper.py

IMMICH_STACK=/path/to/immich-stack
mkdir -p "$IMMICH_STACK/hotfixes"

# Preserve an existing wrapper before replacing it.
if [ -e "$IMMICH_STACK/hotfixes/ffmpeg-motion-photo-wrapper" ]; then
    cp -p "$IMMICH_STACK/hotfixes/ffmpeg-motion-photo-wrapper" \
        "$IMMICH_STACK/hotfixes/ffmpeg-motion-photo-wrapper.backup-$(date +%Y%m%d-%H%M%S)"
fi

install -m 0755 ffmpeg-motion-photo-wrapper \
    "$IMMICH_STACK/hotfixes/ffmpeg-motion-photo-wrapper"
```

Back up your existing Compose override and relevant configuration before editing them. Merge the service configuration in [compose.override.example.yaml](compose.override.example.yaml) into your existing override. Preserve unrelated environment variables, mounts, and customizations. If you already use a differently named wrapper, keep its existing host/container paths and `FFMPEG_PATH` consistent rather than installing a second active wrapper.

From the Immich stack directory, validate and recreate only the server:

```sh
cd "$IMMICH_STACK"
docker compose config --quiet
docker compose up -d --no-deps --force-recreate immich-server
```

Recreation causes a short server interruption and ensures that a file bind mount sees the installed script. Machine learning, Redis/Valkey, PostgreSQL, and source media do not need to be recreated or changed.

Confirm that the server starts successfully and becomes healthy. In Immich, retry thumbnail generation for one known affected asset and check that its preview appears. The menu or job controls may differ between Immich versions.

## Tests

### Synthetic command tests

```sh
bash -n ffmpeg-motion-photo-wrapper
python3 -m unittest -v test_wrapper.py
```

The tests use temporary files, synthetic probe metadata, and stand-in executables. They do not need Docker, FFmpeg, private media, network access, or changes to an Immich installation. They check mapping, pass-through behavior, argument preservation, probe failures, timeout handling, and exit status.

### Optional native thumbnail smoke test

```sh
bash smoke-test.sh ghcr.io/immich-app/immich-server:v3.3.5 /path/to/affected.mp4
```

This starts a disposable container with networking disabled, mounts the sample and wrapper read-only, and writes generated thumbnails only to container-local temporary memory. It does not connect to the application database or write to your library. Docker may first download the requested image if it is not present locally. Only use an image you trust.

The test prints the WebP and JPEG output sizes and checksums. Treat those results as local test data; do not publish them together with private media without reviewing them. It uses internal Immich modules, so its module paths or APIs may need adjustment for another Immich release. A passing smoke test does not replace an application-level check of one affected asset.

## Validation and limitations

The wrapper was tested with the standard ARM64 Immich server image **v3.3.5**. On one affected MP4 sample, its WebP thumbnail and JPEG preview were byte-for-byte identical to those produced by the previous working wrapper. Synthetic tests also cover failure and pass-through cases. No media samples, private paths, host configuration, or production logs are included in this repository.

This is evidence for the specific tested layout, not a guarantee for every Motion Photo or Immich release. Re-test after upgrading Immich: command arguments, container paths, available utilities, and internal APIs can change. If upstream fixes thumbnail stream selection, verify the affected sample without this wrapper before removing it.

## Rollback

To return to a previous wrapper, restore your saved script at the same host path, ensure it remains executable, and recreate only `immich-server` using the command above.

To return to stock FFmpeg, remove only the wrapper-specific `FFMPEG_PATH` setting and bind mount from your Compose configuration, validate it, and recreate the server. Keep unrelated overrides. Reverting the wrapper does not reverse unrelated application upgrades or database changes.

## Upstream background

- [Issue #3421](https://github.com/immich-app/immich/issues/3421): historical Pixel Motion Photo stream-selection problem.
- [PR #3775](https://github.com/immich-app/immich/pull/3775): explicit stream mapping in the video-transcoding path.
- [PR #28162](https://github.com/immich-app/immich/pull/28162): selective metadata bitstream filtering, a related but different problem.
- [PR #30189](https://github.com/immich-app/immich/pull/30189): proposed fallback thumbnail generation; its reviewed version does not add explicit stream mapping.
- [FFmpeg stream-selection documentation](https://ffmpeg.org/ffmpeg.html#Stream-selection).

These references provide background. Their existence or status is not proof that the specific thumbnail failure is fixed in your installed release.
