"""重试装饰器 — tenacity 包装。"""
from __future__ import annotations

import logging

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.providers.exceptions import ProviderError, RateLimitError

log = logging.getLogger(__name__)


def with_retry(provider_name: str, max_attempts: int = 3):
    """标准重试装饰器: 指数退避 1s/2s/4s, 上限 10s。"""

    def _before_sleep(retry_state) -> None:
        log.warning(
            f"[{provider_name}] retry {retry_state.attempt_number}/{max_attempts} "
            f"after error: {retry_state.outcome.exception()}"
        )

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, ProviderError)),
        before_sleep=_before_sleep,
        reraise=True,
    )