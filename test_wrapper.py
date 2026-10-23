"""Synthetic tests: no real media, network, Docker, or Immich required."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


class WrapperTests(unittest.TestCase):
    def test_command_matrix(self):
        with tempfile.TemporaryDirectory(prefix='motion-photo-wrapper-test-') as directory:
            root = Path(directory)
            photos = root / 'photos'
            photos.mkdir()
            sample = photos / 'synthetic sample.mp4'
            sample.touch()
            ffmpeg = root / 'ffmpeg'
            ffmpeg.write_text(f'#!{sys.executable}\nimport sys,json\nprint(json.dumps(sys.argv[1:]))\nsys.exit(23)\n')
            ffprobe = root / 'ffprobe'
            ffprobe.write_text(
                f'#!{sys.executable}\nimport os,sys,time\n'
                'time.sleep(float(os.environ.get("PROBE_SLEEP","0")))\n'
                'print(os.environ.get("PROBE_OUTPUT",""))\n'
                'sys.exit(int(os.environ.get("PROBE_RC","0")))\n'
            )
            ffmpeg.chmod(0o755)
            ffprobe.chmod(0o755)
            source = Path(__file__).with_name('ffmpeg-motion-photo-wrapper').read_text()
            source = source.replace('/usr/bin/ffmpeg', str(ffmpeg))
            source = source.replace('/usr/bin/ffprobe', str(ffprobe))
            source = source.replace('/external/photos', str(photos))
            wrapper = root / 'wrapper'
            wrapper.write_text(source)
            fixture = ('index=0|codec_name=hevc|duration=2.000000|nb_frames=60\n'
                       'index=1|codec_name=hevc|duration=0.000000|nb_frames=1')
            base = ['-i', str(sample), '-frames:v', '1', '/data/thumbs/test.webp']
            cases = [
                ('known layout', base, fixture, 0, True),
                ('existing mapping', base[:-1] + ['-map', '0:0', base[-1]], fixture, 0, False),
                ('failed probe with partial output', base, fixture, 1, False),
                ('multiple inputs', base[:2] + ['-i', str(sample)] + base[2:], fixture, 0, False),
                ('complex filter', base[:-1] + ['-filter_complex', '[0:v]null[v]', base[-1]], fixture, 0, False),
                ('video output', base[:-1] + ['/data/thumbs/test.mp4'], fixture, 0, False),
                ('no single-frame request', ['-i', str(sample), base[-1]], fixture, 0, False),
                ('different codec', base, fixture.replace('hevc', 'h264'), 0, False),
                ('single stream', base, fixture.splitlines()[0], 0, False),
                ('missing duration', base, fixture.replace('duration=0.000000', 'duration=N/A'), 0, False),
                ('empty probe', base, '', 0, False),
                ('large frame count', base, fixture.replace('nb_frames=60', 'nb_frames=' + '9' * 50), 0, True),
                ('JPEG preview', base[:-1] + ['/data/thumbs/test.jpeg'], fixture, 0, True),
            ]
            for name, args, metadata, status, mapped in cases:
                with self.subTest(name=name):
                    env = os.environ.copy()
                    env.update(PROBE_OUTPUT=metadata, PROBE_RC=str(status))
                    result = subprocess.run(['bash', str(wrapper), *args], env=env,
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 23, result.stderr)
                    expected = args[:-1] + ['-map', '0:0', args[-1]] if mapped else args
                    self.assertEqual(json.loads(result.stdout), expected)
                    if mapped:
                        self.assertNotIn(str(sample), result.stderr)
                        self.assertNotIn(sample.name, result.stderr)
            # Shorten only the test copy's deadline to keep the suite quick.
            with self.subTest(name='probe timeout'):
                wrapper.write_text(source.replace('15s', '0.15s'))
                env = os.environ.copy()
                env.update(PROBE_OUTPUT=fixture, PROBE_SLEEP='30', PROBE_RC='0')
                started = time.monotonic()
                result = subprocess.run(['bash', str(wrapper), *base], env=env,
                                        capture_output=True, text=True, timeout=4)
                self.assertEqual(result.returncode, 23, result.stderr)
                self.assertEqual(json.loads(result.stdout), base)
                self.assertLess(time.monotonic() - started, 4)


if __name__ == '__main__':
    unittest.main()
