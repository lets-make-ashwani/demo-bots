import asyncio
import functools
from app.utils.logger import error_logger

def async_retry(tries=3, delay=1.0, backoff=2.0, exceptions=(Exception,)):
    """
    Decorator for retrying async functions with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    error_logger.warning(
                        f"Retrying {func.__name__} in {mdelay:.2f}s due to error: {e}. Tries left: {mtries - 1}"
                    )
                    await asyncio.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            # Last try without catching exceptions
            return await func(*args, **kwargs)
        return wrapper
    return decorator
