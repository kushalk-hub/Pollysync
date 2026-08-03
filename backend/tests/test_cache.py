import pytest
import time
from app.core.cache import cache_get, cache_set, cache_delete_group, cache_clear_all, _l1_cache


def test_cache_set_and_get():
    cache_clear_all()
    cache_set("test_key", {"data": "value"}, ttl=60, group="test")
    result = cache_get("test_key", group="test")
    assert result == {"data": "value"}
    cache_clear_all()


def test_cache_miss_returns_none():
    cache_clear_all()
    result = cache_get("nonexistent_key", group="test")
    assert result is None


def test_cache_delete_group():
    cache_clear_all()
    cache_set("key1", "val1", ttl=60, group="mygroup")
    cache_set("key2", "val2", ttl=60, group="mygroup")
    cache_delete_group("mygroup")
    assert cache_get("key1", group="mygroup") is None
    assert cache_get("key2", group="mygroup") is None
    cache_clear_all()


def test_cache_groups_isolated():
    cache_clear_all()
    cache_set("key", "value_a", ttl=60, group="group_a")
    cache_set("key", "value_b", ttl=60, group="group_b")
    assert cache_get("key", group="group_a") == "value_a"
    assert cache_get("key", group="group_b") == "value_b"
    cache_clear_all()


def test_cache_overwrite():
    cache_clear_all()
    cache_set("key", "original", ttl=60, group="test")
    assert cache_get("key", group="test") == "original"
    cache_set("key", "updated", ttl=60, group="test")
    assert cache_get("key", group="test") == "updated"
    cache_clear_all()


def test_cache_complex_values():
    cache_clear_all()
    complex_data = {
        "temperature": 25.5,
        "humidity": 80,
        "conditions": ["sunny", "windy"],
        "nested": {"key": "value"},
    }
    cache_set("complex", complex_data, ttl=60, group="test")
    result = cache_get("complex", group="test")
    assert result == complex_data
    cache_clear_all()


def test_l1_cache_hit():
    cache_clear_all()
    cache_set("l1_test_key", "l1_only", ttl=60, group="test")
    result = cache_get("l1_test_key", group="test")
    assert result == "l1_only"
