import asyncio
import json
import uuid
from unittest.mock import MagicMock

import httpx
from openai import AsyncOpenAI
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant import agent
from app.assistant.deps import DocumentAgentDeps, TurnRegistry
from app.grounding.validator import GroundingValidator


def test_clarification_uses_json_mode_and_passes_grounding(monkeypatch) -> None:
    requests: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat-test",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [{
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({
                            "answer": "Which company and filing year would you like to research?",
                            "citations": [],
                            "insufficient_evidence": True,
                        }),
                    },
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            },
        )

    client = AsyncOpenAI(
        api_key="test-key",
        base_url="https://model.example/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    provider = OpenAIProvider(openai_client=client)
    monkeypatch.setattr(agent, "OpenAIProvider", lambda **kwargs: provider)
    monkeypatch.setattr(agent, "_document_agent", None)
    retriever = MagicMock()
    registry = TurnRegistry()
    deps = DocumentAgentDeps(
        retriever=retriever,
        registry=registry,
        thread_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    async def run():
        try:
            result = await agent.get_document_agent().run("1", deps=deps)
            validation = await GroundingValidator().validate(result.output, registry)
            return result.output, validation
        finally:
            await client.close()

    answer, validation = asyncio.run(run())

    assert len(requests) == 1
    request = requests[0]
    assert request["response_format"] == {"type": "json_object"}
    assert request["tool_choice"] == "auto"
    assert {tool["function"]["name"] for tool in request["tools"]} == {
        "search_filings", "read_chunk", "read_chunks", "read_surrounding_chunks",
    }
    instructions = "\n".join(message["content"] for message in request["messages"])
    assert '"insufficient_evidence"' in instructions
    assert '"citations"' in instructions
    assert answer.insufficient_evidence
    assert not answer.citations
    assert validation.ok
    retriever.search.assert_not_called()
