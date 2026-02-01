import os
from datetime import timedelta

import pytest

from akande.cache import SQLiteCache


@pytest.fixture
def cache(tmp_path):
    db_path = tmp_path / "test_cache.db"
    return SQLiteCache(db_path, max_size=5, expiration=timedelta(days=1))


def test_set_and_get(cache):
    cache.set("hash1", "response1")
    result = cache.get("hash1")
    assert result == "response1"


def test_get_missing_key(cache):
    result = cache.get("nonexistent")
    assert result is None


def test_cache_overwrite(cache):
    cache.set("hash1", "response1")
    cache.set("hash1", "response2")
    result = cache.get("hash1")
    assert result == "response2"


def test_cache_eviction(cache):
    # Cache max_size is 5; insert 6 items
    for i in range(6):
        cache.set(f"hash{i}", f"response{i}")

    # The oldest entry should have been evicted
    # (exact eviction depends on timestamp granularity)
    stored_count = 0
    for i in range(6):
        if cache.get(f"hash{i}") is not None:
            stored_count += 1
    assert stored_count <= 5


def test_cache_expiration(tmp_path):
    db_path = tmp_path / "test_expire.db"
    cache = SQLiteCache(
        db_path, max_size=10, expiration=timedelta(seconds=-1)
    )
    cache.set("hash1", "response1")
    # With negative expiration, everything is expired
    result = cache.get("hash1")
    assert result is None


def test_cache_stores_dict(cache):
    data = {"key": "value", "number": 42}
    cache.set("hash_dict", data)
    result = cache.get("hash_dict")
    assert result == data


def test_cache_stores_list(cache):
    data = [1, 2, 3, "four"]
    cache.set("hash_list", data)
    result = cache.get("hash_list")
    assert result == data


def test_cache_thread_safety(cache):
    import threading

    errors = []

    def writer(key):
        try:
            cache.set(key, f"value_{key}")
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=writer, args=(f"k{i}",))
        for i in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0


def test_cache_close(tmp_path):
    db_path = tmp_path / "test_close.db"
    cache = SQLiteCache(db_path)
    cache.set("k", "v")
    cache.close()
    assert cache.conn is None


def test_cache_file_permissions(tmp_path):
    db_path = tmp_path / "test_perms.db"
    cache = SQLiteCache(db_path)
    stat = os.stat(str(db_path))
    # Check owner-only read/write (0600)
    assert oct(stat.st_mode)[-3:] == "600"
    cache.close()


def test_cache_has_timestamp_index(cache):
    """Verify the timestamp index exists."""
    with cache.lock:
        cursor = cache.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_cache_timestamp'"
        )
        result = cursor.fetchone()
    assert result is not None
