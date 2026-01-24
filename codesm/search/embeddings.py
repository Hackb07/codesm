import asyncio
import os

import openai

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        from ..auth.credentials import CredentialStore

        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            store = CredentialStore()
            api_key = store.get_api_key("openai")

        if not api_key:
            raise RuntimeError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment variable or configure it in the app."
            )
        _client = openai.OpenAI(api_key=api_key)
    return _client


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    client = _get_client()

    all_embeddings = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch = [t[:8000] for t in batch]

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda b=batch: client.embeddings.create(
                model="text-embedding-3-small",
                input=b,
            ),
        )

        for item in response.data:
            all_embeddings.append(item.embedding)

    return all_embeddings
