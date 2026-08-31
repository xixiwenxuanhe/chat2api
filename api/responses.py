"""Small, text-only OpenAI Responses compatibility adapter."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any


def messages_from_input(value: Any, instructions: Any = None) -> list[dict[str, Any]]:
    messages = []
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions.strip()})
    if isinstance(value, str):
        if value.strip(): messages.append({"role": "user", "content": value.strip()})
    elif isinstance(value, dict):
        content = value.get("content", value.get("text", ""))
        if isinstance(content, list):
            content = "".join(str(p.get("text") or "") for p in content if isinstance(p, dict))
        if str(content).strip(): messages.append({"role": value.get("role", "user"), "content": content})
    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, dict): continue
            content = item.get("content", item.get("text", ""))
            if isinstance(content, list):
                content = "".join(str(p.get("text") or "") for p in content if isinstance(p, dict))
            if str(content).strip(): messages.append({"role": item.get("role", "user"), "content": content})
    return messages


def to_chat_request(body: dict[str, Any]) -> dict[str, Any]:
    request = {"model": str(body.get("model") or "auto"),
               "messages": messages_from_input(body.get("input"), body.get("instructions")),
               "stream": bool(body.get("stream", False))}
    if body.get("max_output_tokens") is not None: request["max_tokens"] = body["max_output_tokens"]
    if isinstance(body.get("reasoning"), dict) and body["reasoning"].get("effort"):
        request["reasoning_effort"] = body["reasoning"]["effort"]
    return request


def completed(chat: dict[str, Any], model: str) -> dict[str, Any]:
    message = ((chat.get("choices") or [{}])[0].get("message") or {})
    text = str(message.get("content") or "")
    item = {"id": "msg_" + uuid.uuid4().hex, "type": "message", "status": "completed",
            "role": "assistant", "content": [{"type": "output_text", "text": text, "annotations": []}]}
    response = {"id": "resp_" + uuid.uuid4().hex, "object": "response", "created_at": int(time.time()),
                "status": "completed", "error": None, "incomplete_details": None, "model": model,
                "output": [item], "parallel_tool_calls": False}
    if chat.get("usage"): response["usage"] = chat["usage"]
    return response


async def stream(chunks, model):
    response_id, item_id, created, text = "resp_" + uuid.uuid4().hex, "msg_" + uuid.uuid4().hex, int(time.time()), ""
    def event(kind, **fields):
        return f"event: {kind}\ndata: {json.dumps({'type': kind, **fields}, ensure_ascii=False)}\n\n"
    yield event("response.created", response={"id": response_id, "object": "response", "created_at": created, "status": "in_progress", "model": model, "output": []})
    yield event("response.output_item.added", response_id=response_id, output_index=0, item={"id": item_id, "type": "message", "status": "in_progress", "role": "assistant"})
    async for raw in chunks:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        for part in line.splitlines():
            if not part.startswith("data:"): continue
            payload = part[5:].strip()
            if not payload or payload == "[DONE]": continue
            try: data = json.loads(payload)
            except (TypeError, ValueError): continue
            delta = ((data.get("choices") or [{}])[0].get("delta") or {})
            if delta.get("content"):
                text += delta["content"]
                yield event("response.output_text.delta", response_id=response_id, item_id=item_id, output_index=0, content_index=0, delta=delta["content"])
    item = {"id": item_id, "type": "message", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": text, "annotations": []}]}
    yield event("response.output_text.done", response_id=response_id, item_id=item_id, output_index=0, content_index=0, text=text)
    yield event("response.output_item.done", response_id=response_id, output_index=0, item=item)
    yield event("response.completed", response={"id": response_id, "object": "response", "created_at": created, "status": "completed", "error": None, "incomplete_details": None, "model": model, "output": [item], "parallel_tool_calls": False})
    yield "data: [DONE]\n\n"
