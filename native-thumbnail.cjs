// Optional smoke test for the internal thumbnail API in Immich v3.3.5.
const { MediaRepository } = require('/usr/src/app/server/dist/repositories/media.repository.js');
const { ThumbnailConfig } = require('/usr/src/app/server/dist/utils/media.js');
const { TranscodeTarget } = require('/usr/src/app/server/dist/enum.js');
const fs = require('fs');
const crypto = require('crypto');
const logger = {
  setContext() {}, debug() {}, log() {}, warn() {},
  error(value) { console.error(String(value).slice(-1200)); },
  isLevelEnabled() { return false; },
};
(async () => {
  const media = new MediaRepository(logger);
  const input = '/external/photos/sample.mp4';
  const probe = await media.probe(input);
  if (!probe.videoStreams.length) throw new Error('No video stream found');
  for (const [format, resolution] of [['webp', '250'], ['jpeg', '1440']]) {
    const config = ThumbnailConfig.create({ targetResolution: resolution, tonemap: 'disabled', threads: 1 });
    const options = config.getCommand(TranscodeTarget.Video, probe.videoStreams[0], undefined, probe.format);
    const output = `/data/thumbs/smoke-test.${format}`;
    await media.transcode(input, output, options);
    const bytes = fs.readFileSync(output);
    if (!bytes.length) throw new Error('Empty thumbnail output');
    console.log(JSON.stringify({ format, bytes: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex') }));
  }
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
