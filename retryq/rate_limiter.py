import time
import redis
from typing import Optional


class RateLimiter:
    """
    Token bucket rate limiter backed by Redis.
    Limits how many tasks can be dequeued / processed per second.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        max_tokens: int = 10,
        refill_rate: float = 1.0,
        ttl: int = 60,
    ):
        """
        :param redis_client: Redis connection.
        :param key:          Redis key used to store the bucket state.
        :param max_tokens:   Maximum burst capacity.
        :param refill_rate:  Tokens added per second.
        :param ttl:          Key expiry in seconds (safety net).
        """
        self.redis = redis_client
        self.key = key
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.ttl = ttl

        self._tokens_field = "tokens"
        self._last_field = "last_refill"

    def _now(self) -> float:
        return time.monotonic()

    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire *tokens* from the bucket.
        Returns True if the tokens were granted, False if rate-limited.
        """
        now = self._now()

        pipe = self.redis.pipeline()
        pipe.hgetall(self.key)
        results = pipe.execute()
        state = results[0]

        if state:
            current_tokens = float(state.get(b"tokens", self.max_tokens))
            last_refill = float(state.get(b"last_refill", now))
        else:
            current_tokens = float(self.max_tokens)
            last_refill = now

        elapsed = max(0.0, now - last_refill)
        refilled = elapsed * self.refill_rate
        current_tokens = min(self.max_tokens, current_tokens + refilled)

        if current_tokens < tokens:
            return False

        current_tokens -= tokens

        pipe = self.redis.pipeline()
        pipe.hset(self.key, mapping={"tokens": current_tokens, "last_refill": now})
        pipe.expire(self.key, self.ttl)
        pipe.execute()

        return True

    def available_tokens(self) -> float:
        """Return the current (approximate) number of available tokens."""
        state = self.redis.hgetall(self.key)
        if not state:
            return float(self.max_tokens)
        tokens = float(state.get(b"tokens", self.max_tokens))
        last_refill = float(state.get(b"last_refill", self._now()))
        elapsed = max(0.0, self._now() - last_refill)
        return min(self.max_tokens, tokens + elapsed * self.refill_rate)

    def reset(self) -> None:
        """Delete the bucket key, effectively resetting the limiter."""
        self.redis.delete(self.key)
