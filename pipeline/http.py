import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger()

# Network blips and timeouts are worth retrying; so are 429/5xx, but other 4xx are not.
_RETRYABLE_EXC = (httpx.TransportError, httpx.TimeoutException)


def _is_retryable_status(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


def _log_retry(state) -> None:
    logger.warning(
        "http.retry",
        attempt=state.attempt_number,
        error=str(state.outcome.exception()) if state.outcome else None,
    )


async def get_json(client: httpx.AsyncClient, url: str) -> object:
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        retry=retry_if_exception_type(_RETRYABLE_EXC) | retry_if_exception(_is_retryable_status),
        before_sleep=_log_retry,
    )
    async def _do() -> object:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

    return await _do()
