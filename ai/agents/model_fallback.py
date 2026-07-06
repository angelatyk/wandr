"""Gemini model fallback helper.

Wraps generate_content with an ordered list of models (primary + fallbacks).
Falls through to the next model only for transient or quota errors — auth,
validation, and content-policy errors are re-raised immediately so callers
aren't silently retried on problems that won't resolve with a different model.
"""

import asyncio
import logging
from typing import Sequence

from google.genai.errors import ClientError, ServerError

logger = logging.getLogger(__name__)

_QUOTA_TOKENS = ("resource_exhausted", "quota", "rate limit", "429")
_TRANSIENT_TOKENS = ("503", "unavailable", "high demand", "overloaded")
_NOT_FOUND_TOKENS = ("not_found", "is not found", "not supported for generatecontent")

_GEMINI_API_ERRORS = (ClientError, ServerError)


def _is_quota_error(exc: Exception) -> bool:
    return any(token in str(exc).lower() for token in _QUOTA_TOKENS)


def _is_transient_error(exc: Exception) -> bool:
    return _is_quota_error(exc) or any(token in str(exc).lower() for token in _TRANSIENT_TOKENS)


def _is_model_unavailable_error(exc: Exception) -> bool:
    return any(token in str(exc).lower() for token in _NOT_FOUND_TOKENS)


def _should_try_next_model(exc: Exception, index: int, model_count: int) -> bool:
    if index >= model_count - 1:
        return False
    return _is_model_unavailable_error(exc) or _is_transient_error(exc)


async def generate_with_fallback(
    *,
    client,
    primary_model: str,
    fallback_models: Sequence[str],
    contents,
    config,
    call_label: str,
):
    """
    Call Gemini with a primary model and optional fallback models.

    Fallback is attempted for transient Gemini failures (quota, overload, missing
    model) so we do not mask validation or auth/config errors.
    """
    models = [primary_model, *[m for m in fallback_models if m and m != primary_model]]
    last_error: Exception | None = None

    for index, model_name in enumerate(models):
        try:
            if index > 0:
                logger.info(
                    "%s attempting fallback model=%s.",
                    call_label,
                    model_name,
                )
            return await client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
        except _GEMINI_API_ERRORS as exc:
            last_error = exc
            if not _should_try_next_model(exc, index, len(models)):
                raise
            next_model = models[index + 1]
            reason = "unavailable" if _is_model_unavailable_error(exc) else "transient error"
            logger.warning(
                "%s model=%s hit %s — trying fallback model=%s.",
                call_label,
                model_name,
                reason,
                next_model,
            )
            # Brief pause before the next model on overload-style failures.
            if _is_transient_error(exc) and not _is_quota_error(exc):
                await asyncio.sleep(1.5)
            continue

    if last_error:
        raise last_error
    raise RuntimeError(f"{call_label} failed without a response")
