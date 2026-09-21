import tempfile
import unittest
from pathlib import Path

from z0archy_core.cache import SqliteJsonCache


class CacheTests(unittest.TestCase):
    def test_request_key_is_order_stable_and_stale_entries_remain_available(self):
        with tempfile.TemporaryDirectory() as td:
            cache = SqliteJsonCache(Path(td) / "cache.sqlite3")
            try:
                a = cache.request_key("query  Q { x }", {"b": 2, "a": 1})
                b = cache.request_key("query Q {   x }", {"a": 1, "b": 2})
                self.assertEqual(a, b)
                cache.put(a, {"data": {"x": 1}}, ttl_seconds=-1)
                self.assertIsNone(cache.get(a))
                self.assertEqual(cache.get(a, allow_stale=True)["data"]["x"], 1)
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()
