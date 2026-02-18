"""Service for generating embeddings via OpenAI's text-embedding-3-small."""

import logging

from openai import AsyncOpenAI, APIError, RateLimitError

from app.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
MAX_BATCH_SIZE = 2048  # OpenAI limit per request
MAX_TOKEN_ESTIMATE = 8000  # text-embedding-3-small limit is 8192 tokens
MAX_CHARS = MAX_TOKEN_ESTIMATE * 3  # ~3 chars per token conservative estimate

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of text strings.

    Automatically batches requests to stay within OpenAI's 2048-per-request
    limit. Returns vectors in the same order as the input texts.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors (each a list of floats).

    Raises:
        RuntimeError: If the OpenAI API call fails after retries.
    """
    if not texts:
        return []

    texts = _truncate_oversized(texts)

    all_embeddings: list[list[float]] = []

    for batch_start in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[batch_start : batch_start + MAX_BATCH_SIZE]
        embeddings = await _embed_batch(batch)
        all_embeddings.extend(embeddings)

    return all_embeddings


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a single batch (≤2048 texts).

    Retries once on rate-limit errors with a short backoff.
    """
    import asyncio

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = await _client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
            )
            # Response items may not be in order — sort by index
            sorted_data = sorted(response.data, key=lambda d: d.index)
            return [item.embedding for item in sorted_data]

        except RateLimitError:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning("Rate limited by OpenAI, retrying in %ds...", wait)
                await asyncio.sleep(wait)
            else:
                raise RuntimeError(
                    "OpenAI rate limit exceeded after retries. Try again later."
                )

        except APIError as e:
            raise RuntimeError(f"OpenAI API error: {e}") from e


def _truncate_oversized(texts: list[str]) -> list[str]:
    """Truncate any text that would exceed the embedding model's token limit.

    Uses len(text) // 3 as a conservative chars-to-tokens estimate.
    """
    result: list[str] = []
    for text in texts:
        if len(text) > MAX_CHARS:
            logger.warning(
                "Truncating chunk from %d to %d chars (estimated %d→%d tokens)",
                len(text), MAX_CHARS, len(text) // 3, MAX_TOKEN_ESTIMATE,
            )
            result.append(text[:MAX_CHARS])
        else:
            result.append(text)
    return result
