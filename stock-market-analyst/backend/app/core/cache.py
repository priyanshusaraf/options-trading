"""
Disk-backed cache using diskcache.
All expensive API calls and computed results go through here.
"""
import functools
import hashlib
import json
from typing import Any, Callable, Optional
import diskcache
from .config import get_settings
from .logging import logger


_cache: Optional[diskcache.Cache] = None


def get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        settings = get_settings()
        _cache = diskcache.Cache(str(settings.cache_dir), size_limit=2**31)  # 2 GB
    return _cache


def cache_key(*args, **kwargs) -> str:
    payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def cached(ttl: Optional[int] = None, prefix: str = "") -> Callable:
    """Decorator: cache the return value of any function."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            settings = get_settings()
            key = prefix + ":" + fn.__qualname__ + ":" + cache_key(*args, **kwargs)
            result = get_cache().get(key)
            if result is not None:
                logger.debug(f"Cache HIT  | {fn.__qualname__}")
                return result
            logger.debug(f"Cache MISS | {fn.__qualname__}")
            result = fn(*args, **kwargs)
            expire = ttl if ttl is not None else settings.cache_ttl_seconds
            get_cache().set(key, result, expire=expire)
            return result

        return wrapper

    return decorator


def invalidate(prefix: str) -> int:
    """Remove all keys matching a prefix. Returns count removed."""
    cache = get_cache()
    removed = 0
    for key in list(cache.iterkeys()):
        if isinstance(key, str) and key.startswith(prefix):
            del cache[key]
            removed += 1
    return removed


def cache_stats() -> dict[str, Any]:
    cache = get_cache()
    return {
        "size_bytes": cache.volume(),
        "count": len(cache),
        "directory": str(cache.directory),
    }
