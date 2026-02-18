"""Tests for the embedder service."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embedder import (
    embed_texts,
    _truncate_oversized,
    MAX_BATCH_SIZE,
    MAX_CHARS,
)


async def test_empty_input_returns_empty():
    """embed_texts([]) should return [] without calling the API."""
    result = await embed_texts([])
    assert result == []


async def test_truncate_oversized_leaves_short_texts():
    """Texts under MAX_CHARS should pass through unchanged."""
    texts = ["short text", "another one"]
    result = _truncate_oversized(texts)
    assert result == texts


async def test_truncate_oversized_truncates_long_texts():
    """Texts over MAX_CHARS should be truncated to MAX_CHARS."""
    long_text = "x" * (MAX_CHARS + 5000)
    result = _truncate_oversized([long_text, "short"])
    assert len(result[0]) == MAX_CHARS
    assert result[1] == "short"


async def test_single_batch_calls_api_once():
    """A small number of texts should result in exactly one API call."""
    fake_embedding = [0.1] * 1536

    # Build a mock response object that matches OpenAI's structure
    mock_item = MagicMock()
    mock_item.index = 0
    mock_item.embedding = fake_embedding

    mock_response = MagicMock()
    mock_response.data = [mock_item]

    mock_create = AsyncMock(return_value=mock_response)

    with patch("app.services.embedder._client") as mock_client:
        mock_client.embeddings.create = mock_create

        result = await embed_texts(["hello"])

    assert len(result) == 1
    assert result[0] == fake_embedding
    mock_create.assert_awaited_once()


async def test_batching_splits_large_inputs():
    """Inputs larger than MAX_BATCH_SIZE should be split into multiple API calls."""
    fake_embedding = [0.1] * 1536
    num_texts = MAX_BATCH_SIZE + 100  # triggers 2 batches

    def make_response(texts):
        items = []
        for i in range(len(texts)):
            item = MagicMock()
            item.index = i
            item.embedding = fake_embedding
            items.append(item)
        resp = MagicMock()
        resp.data = items
        return resp

    mock_create = AsyncMock(side_effect=lambda **kwargs: make_response(kwargs["input"]))

    with patch("app.services.embedder._client") as mock_client:
        mock_client.embeddings.create = mock_create

        result = await embed_texts(["text"] * num_texts)

    assert len(result) == num_texts
    assert mock_create.await_count == 2  # 2048 + 100 = 2 batches


async def test_result_order_preserved():
    """Embeddings should be returned in the same order as input texts,
    even if the API returns them out of order."""
    emb_a = [1.0] * 10
    emb_b = [2.0] * 10

    # Simulate API returning items out of order
    item_b = MagicMock()
    item_b.index = 1
    item_b.embedding = emb_b

    item_a = MagicMock()
    item_a.index = 0
    item_a.embedding = emb_a

    mock_response = MagicMock()
    mock_response.data = [item_b, item_a]  # reversed order

    mock_create = AsyncMock(return_value=mock_response)

    with patch("app.services.embedder._client") as mock_client:
        mock_client.embeddings.create = mock_create

        result = await embed_texts(["text_a", "text_b"])

    assert result[0] == emb_a
    assert result[1] == emb_b
