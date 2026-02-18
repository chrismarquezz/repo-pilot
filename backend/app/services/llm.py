"""Service for Claude API calls with streaming."""

import logging
from collections.abc import AsyncGenerator

import anthropic

from app.config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = (
    "You are RepoPilot, an AI assistant that answers questions about codebases. "
    "You have been given relevant code snippets from the repository. "
    "Always reference specific filenames and line numbers in your answers. "
    "If the retrieved code doesn't contain enough information to answer, "
    "say so honestly. Be concise and specific."
)

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


def _build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context block for the prompt."""
    sections: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        header = (
            f"[Chunk {i}] {chunk['filename']} "
            f"(lines {chunk['start_line']}-{chunk['end_line']})"
        )
        sections.append(f"{header}\n```\n{chunk['content']}\n```")
    return "\n\n".join(sections)


async def stream_response(
    question: str, context_chunks: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream Claude's answer token-by-token.

    Args:
        question: The user's natural language question.
        context_chunks: Relevant code chunks from the vector store.

    Yields:
        Text delta strings as Claude generates them.

    Raises:
        RuntimeError: If the Anthropic API call fails.
    """
    context = _build_context(context_chunks)
    user_message = (
        f"## Retrieved Code Context:\n{context}\n\n"
        f"## User Question:\n{question}"
    )

    try:
        async with _client.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    except anthropic.APIError as e:
        raise RuntimeError(f"Claude API error: {e}") from e
