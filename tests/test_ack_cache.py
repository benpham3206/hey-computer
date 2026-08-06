import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ack_cache import ensure_ack_cache  # noqa: E402


class AckCacheTests(unittest.TestCase):
    def test_existing_nonempty_cache_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "listening.mp3"
            target.write_bytes(b"cached-audio")
            calls = []
            self.assertTrue(ensure_ack_cache(target, calls.append))
            self.assertEqual([], calls)

    def test_missing_cache_is_generated_and_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "listening.mp3"

            def generate(path):
                path.write_bytes(b"generated-audio")

            self.assertTrue(ensure_ack_cache(target, generate))
            self.assertEqual(b"generated-audio", target.read_bytes())

    def test_empty_generated_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "listening.mp3"

            def generate(path):
                path.touch()

            self.assertFalse(ensure_ack_cache(target, generate))


if __name__ == "__main__":
    unittest.main()
