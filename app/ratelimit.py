from fastapi import HTTPException, Request

from app.cache import redis_client


def rate_limit(name: str, limit: int, window_seconds: int):
    def checker(request: Request):
        ip = request.client.host if request.client else "unknown"
        key = f"rate:{name}:{ip}"

        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()

        if count > limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Try again later.",
            )

    return checker