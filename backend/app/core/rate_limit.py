from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

# Single shared limiter — keyed by client IP address.
# Mount it on app.state.limiter in main.py, register the RateLimitExceeded
# exception handler there too, and add SlowAPIMiddleware so default_limits
# below actually gets enforced on every route that doesn't set its own
# stricter @limiter.limit(...) (login, forgot-password, embed-generate,
# ai-process, ...) -- without that middleware, default_limits is inert and
# only explicitly decorated routes get limited at all.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[get_settings().rate_limit_default],
)
