from django.core.cache import cache


def is_rate_limited(key, max_per_minute):
    cache_key = f"ratelimit:{key}"
    current = cache.get(cache_key, 0)
    if current >= max_per_minute:
        return True
    cache.set(cache_key, current + 1, timeout=60)
    return False
