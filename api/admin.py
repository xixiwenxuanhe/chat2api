import hashlib
import hmac
import time
import types

from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

import utils.configs as configs
import utils.globals as globals
from app import app
from chatgpt.chatFormat import sanitize_openai_stream
from chatgpt.credentials import (
    clear_credential_errors,
    delete_credential,
    refresh_credential,
    session_payload,
    upsert_credential,
)
from chatgpt.ChatService import ChatService
from utils.retry import async_retry
from chatgpt.modelCatalog import get_model_catalog, to_openai_model_list
from api.responses import completed as responses_completed, stream as responses_stream, to_chat_request


COOKIE_NAME = "chat2api_admin"


def _admin_secret():
    return configs.admin_key or (configs.authorization_list[0] if configs.authorization_list else None)


def _cookie_value(secret):
    return hmac.new(secret.encode(), b"chat2api-admin", hashlib.sha256).hexdigest()


async def require_admin(request: Request):
    secret = _admin_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="ADMIN_KEY is not configured")
    authorization = request.headers.get("authorization", "")
    bearer = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    cookie = request.cookies.get(COOKIE_NAME, "")
    if not (hmac.compare_digest(bearer, secret) or hmac.compare_digest(cookie, _cookie_value(secret))):
        raise HTTPException(status_code=401, detail="Invalid management key")


def _credential_record(credential):
    return {
        "id": credential["id"],
        "account_id": credential.get("account_id"),
        "email": credential.get("email"),
        "status": credential.get("status", "active"),
        "access_expires_at": credential.get("access_expires_at"),
        "updated_at": credential.get("updated_at"),
        "last_error": credential.get("last_error"),
    }


@app.get("/admin")
async def admin_page():
    return FileResponse("admin_dist/index.html")


@app.post("/admin/api/login")
async def admin_login(request: Request):
    secret = _admin_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="ADMIN_KEY is not configured")
    data = await request.json()
    submitted = str(data.get("key", ""))
    if not hmac.compare_digest(submitted, secret):
        raise HTTPException(status_code=401, detail="Invalid management key")
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        COOKIE_NAME,
        _cookie_value(secret),
        max_age=604800,
        httponly=True,
        samesite="strict",
        path="/admin",
    )
    return response


@app.post("/admin/api/logout")
async def admin_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/admin")
    return {"status": "ok"}


@app.get("/admin/api/status", dependencies=[Depends(require_admin)])
async def admin_status():
    active = sum(item.get("status") != "error" for item in globals.credential_list)
    return {
        "service": "online",
        "credentials": len(globals.credential_list),
        "active_credentials": active,
        "error_credentials": len(globals.credential_list) - active,
        "gateway_enabled": configs.enable_gateway,
        "proxy_configured": bool(configs.proxy_url_list),
        "timestamp": int(time.time()),
    }


@app.get("/admin/api/credentials", dependencies=[Depends(require_admin)])
async def admin_credentials():
    return {"data": [_credential_record(credential) for credential in globals.credential_list]}


@app.get("/admin/api/credentials/{credential_id}", dependencies=[Depends(require_admin)])
async def admin_credential_detail(credential_id: str):
    credential = next((item for item in globals.credential_list if item.get("id") == credential_id), None)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"id": credential_id, "session": session_payload(credential)}


@app.post("/admin/api/credentials", dependencies=[Depends(require_admin)])
async def admin_add_credentials(request: Request):
    data = await request.json()
    credential, created = await upsert_credential(data.get("content", ""))
    return {
        "status": "ok",
        "created": created,
        "credential": _credential_record(credential),
        "total": len(globals.credential_list),
    }


@app.delete("/admin/api/credentials/{credential_id}", dependencies=[Depends(require_admin)])
async def admin_delete_credential(credential_id: str):
    await delete_credential(credential_id)
    return {"status": "ok"}


@app.post("/admin/api/credentials/{credential_id}/refresh", dependencies=[Depends(require_admin)])
async def admin_refresh_credential(credential_id: str):
    credential = await refresh_credential(credential_id)
    return {"status": "ok", "credential": _credential_record(credential)}


@app.delete("/admin/api/errors", dependencies=[Depends(require_admin)])
async def admin_clear_errors():
    await clear_credential_errors()
    return {"status": "ok"}


@app.get("/admin/api/models", dependencies=[Depends(require_admin)])
async def admin_models():
    if not configs.authorization_list:
        raise HTTPException(status_code=503, detail="AUTHORIZATION is not configured")
    catalog, updated_at = await get_model_catalog(configs.authorization_list[0])
    response = to_openai_model_list(catalog)
    response["default_model"] = catalog.get("default_model_slug")
    response["model_picker_version"] = catalog.get("model_picker_version")
    response["updated_at"] = updated_at
    return response


@app.post("/admin/api/models/refresh", dependencies=[Depends(require_admin)])
async def admin_refresh_models():
    if not configs.authorization_list:
        raise HTTPException(status_code=503, detail="AUTHORIZATION is not configured")
    catalog, updated_at = await get_model_catalog(configs.authorization_list[0], refresh=True)
    response = to_openai_model_list(catalog)
    response["default_model"] = catalog.get("default_model_slug")
    response["model_picker_version"] = catalog.get("model_picker_version")
    response["updated_at"] = updated_at
    return response


@app.post("/admin/api/playground/chat", dependencies=[Depends(require_admin)])
async def admin_playground_chat(request: Request):
    data = await request.json()
    model = data.get("model")
    messages = data.get("messages")
    stream = bool(data.get("stream", False))
    protocol = str(data.get("protocol") or "chat.completions").strip().lower()
    if protocol not in {"chat.completions", "responses"}:
        raise HTTPException(status_code=400, detail="unsupported protocol")
    if not isinstance(model, str) or not model.strip() or not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="model and messages are required")
    request_data = {"model": model.strip(), "messages": messages, "stream": stream}
    if protocol == "responses":
        request_data = to_chat_request({"model": model.strip(), "input": messages, "stream": stream})
    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty", "max_tokens"):
        if key in data and data[key] is not None:
            request_data[key] = data[key]

    async def process():
        service = ChatService(configs.authorization_list[0])
        try:
            await service.set_dynamic_data(request_data)
            await service.get_chat_requirements()
            await service.prepare_send_conversation()
            res = await service.send_conversation()
            if isinstance(res, types.AsyncGeneratorType):
                background = BackgroundTask(service.close_client)
                return StreamingResponse(
                    responses_stream(res, model) if protocol == "responses" else sanitize_openai_stream(res),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                    background=background,
                )
            await service.close_client()
            return responses_completed(res, model) if protocol == "responses" else res
        except HTTPException as e:
            await service.close_client()
            raise
        except Exception as e:
            await service.close_client()
            raise HTTPException(status_code=500, detail=str(e))

    return await async_retry(process)
