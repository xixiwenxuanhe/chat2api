from fastapi import HTTPException

from chatgpt.ChatService import ChatService
from utils.configs import history_disabled


async def fetch_model_catalog(req_token):
    service = ChatService(req_token)
    try:
        await service.set_dynamic_data({"model": "auto", "messages": []})
        response = await service.s.get(
            f"{service.base_url}/models",
            headers=service.base_headers,
            params={"history_and_training_disabled": str(history_disabled).lower()},
            timeout=15,
        )
        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.json())
            except Exception:
                detail = response.text[:500]
            raise HTTPException(status_code=response.status_code, detail=detail)
        return response.json()
    finally:
        await service.close_client()


def to_openai_model_list(catalog):
    models = []
    for model in catalog.get("models", []):
        slug = model.get("slug")
        if not slug:
            continue
        models.append({
            "id": slug,
            "object": "model",
            "created": 0,
            "owned_by": "chatgpt",
            "name": model.get("title", slug),
            "description": model.get("description"),
            "context_length": model.get("max_tokens"),
        })
    return {"object": "list", "data": models}
