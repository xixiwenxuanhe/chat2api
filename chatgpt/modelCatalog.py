import asyncio
import json
import os
import re
import time

from fastapi import HTTPException

from chatgpt.ChatService import ChatService
from chatgpt.credentials import is_expired_error, refresh_credential
import utils.globals as globals
from utils.configs import history_disabled

catalog_lock = asyncio.Lock()


async def get_model_catalog(req_token, refresh=False):
    async with catalog_lock:
        if not refresh and os.path.exists(globals.MODEL_CATALOG_FILE):
            try:
                with open(globals.MODEL_CATALOG_FILE, "r", encoding="utf-8") as file:
                    cached = json.load(file)
                if isinstance(cached.get("catalog"), dict):
                    return cached["catalog"], cached.get("updated_at")
            except (OSError, ValueError, AttributeError):
                pass

        catalog = await _fetch_model_catalog(req_token)
        updated_at = int(time.time())
        temp_file = globals.MODEL_CATALOG_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump({"updated_at": updated_at, "catalog": catalog}, file, ensure_ascii=False)
        os.replace(temp_file, globals.MODEL_CATALOG_FILE)
        return catalog, updated_at


async def _fetch_model_catalog(req_token):
    for attempt in range(2):
        service = ChatService(req_token)
        try:
            await service.set_dynamic_data({"model": "auto", "messages": []})
            response = await service.s.get(
                f"{service.base_url}/models",
                headers=service.base_headers,
                params={"history_and_training_disabled": str(history_disabled).lower()},
                timeout=15,
            )
            if response.status_code == 200:
                return response.json()
            try:
                detail = response.json().get("detail", response.json())
            except Exception:
                detail = response.text[:500]
            error = HTTPException(status_code=response.status_code, detail=detail)
            if attempt == 0 and is_expired_error(error):
                await refresh_credential(service.req_token)
                continue
            raise error
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
            "max_tokens": model.get("max_tokens"),
            "context_length": model.get("max_tokens"),
        })
    parsed = {model["id"]: _model_parts(model["id"]) for model in models}
    models.sort(key=lambda model: _model_sort_key(model["id"], parsed[model["id"]]))
    return {"object": "list", "data": models}


def _model_parts(value):
    parts = re.findall(r"\d+|[a-z]+", value, re.IGNORECASE)
    number_indexes = [index for index, part in enumerate(parts) if part.isdigit()]
    if not number_indexes:
        return None, []

    version_numbers = [int(parts[index]) for index in number_indexes[:2]]
    version_numbers += [0] * (2 - len(version_numbers))
    suffix_start = number_indexes[min(1, len(number_indexes) - 1)] + 1
    suffix = [part.casefold() for part in parts[suffix_start:] if not part.isdigit()]
    return tuple(version_numbers), suffix


def _model_sort_key(value, parsed):
    version_numbers, suffix = parsed
    if not version_numbers:
        return 2, value.casefold()

    if len(suffix) >= 2:
        return 1, suffix[-1], -version_numbers[0], -version_numbers[1], len(suffix), tuple(suffix), value.casefold()

    if not suffix:
        variant_rank = 0
    elif suffix == ["thinking"]:
        variant_rank = 1
    else:
        variant_rank = 2
    return 0, -version_numbers[0], -version_numbers[1], variant_rank, tuple(suffix), value.casefold()
