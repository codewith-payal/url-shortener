import json

import redis

redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

CACHE_TTL_SECONDS = 3600  # keep a link in the cache for 1 hour


def _key(short_code: str) -> str:
    return f"link:{short_code}"


def get_cached_link(short_code: str) -> dict | None:
    raw = redis_client.get(_key(short_code))
    return json.loads(raw) if raw else None


def set_cached_link(short_code: str, link_id: int, url: str) -> None:
    value = json.dumps({"id": link_id, "url": url})
    redis_client.set(_key(short_code), value, ex=CACHE_TTL_SECONDS)