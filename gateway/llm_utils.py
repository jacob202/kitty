import time
import logging
from typing import Callable, Any

logger = logging.getLogger("kitty.llm_utils")

def retry_with_backoff(func: Callable, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    """Retries a function with exponential backoff on 429 errors."""
    def wrapper(*args, **kwargs):
        retries = 0
        while retries <= max_retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Check for 429 Too Many Requests
                is_429 = False
                if hasattr(e, "response") and e.response is not None:
                    if e.response.status_code == 429:
                        is_429 = True
                elif "429" in str(e):
                    is_429 = True
                
                if is_429 and retries < max_retries:
                    delay = min(base_delay * (2 ** retries), max_delay)
                    logger.warning("LLM rate limit (429) hit. Retrying in %.1fs (attempt %d/%d)...", delay, retries + 1, max_retries)
                    time.sleep(delay)
                    retries += 1
                else:
                    raise e
    return wrapper
