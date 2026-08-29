import asyncio
import hashlib
import hmac
import json
import time

from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

import utils.configs as configs
import utils.globals as globals
from app import app, templates
from chatgpt.modelCatalog import fetch_model_catalog, to_openai_model_list


COOKIE_NAME = "chat2api_admin"
token_lock = asyncio.Lock()


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


def _token_id(token):
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _token_type(token):
    if token.startswith("eyJ"):
        return "access_token"
    if len(token) == 45:
        return "refresh_token"
    return "token"


def _masked_token(token):
    if len(token) <= 18:
        return token[:4] + "..." + token[-3:]
    return token[:10] + "..." + token[-8:]


def _credential_record(token):
    return {
        "id": _token_id(token),
        "type": _token_type(token),
        "masked": _masked_token(token),
        "status": "error" if token in globals.error_token_list else "active",
    }


def _extract_tokens(content):
    content = content.strip()
    if not content:
        return []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        token = payload.get("accessToken") or payload.get("access_token")
        if isinstance(token, str) and token.strip():
            return [token.strip()]
        nested = payload.get("tokens")
        if isinstance(nested, dict):
            token = nested.get("access_token") or nested.get("accessToken")
            if isinstance(token, str) and token.strip():
                return [token.strip()]
        raise HTTPException(status_code=400, detail="No access token found in JSON")
    return [line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _persist_tokens():
    with open(globals.TOKENS_FILE, "w", encoding="utf-8") as file:
        for token in globals.token_list:
            file.write(token + "\n")
    with open(globals.ERROR_TOKENS_FILE, "w", encoding="utf-8") as file:
        for token in globals.error_token_list:
            file.write(token + "\n")


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


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
    active = len(set(globals.token_list) - set(globals.error_token_list))
    return {
        "service": "online",
        "credentials": len(set(globals.token_list)),
        "active_credentials": active,
        "error_credentials": len(set(globals.error_token_list)),
        "gateway_enabled": configs.enable_gateway,
        "proxy_configured": bool(configs.proxy_url_list),
        "timestamp": int(time.time()),
    }


@app.get("/admin/api/credentials", dependencies=[Depends(require_admin)])
async def admin_credentials():
    return {"data": [_credential_record(token) for token in dict.fromkeys(globals.token_list)]}


@app.post("/admin/api/credentials", dependencies=[Depends(require_admin)])
async def admin_add_credentials(request: Request):
    data = await request.json()
    tokens = _extract_tokens(str(data.get("content", "")))
    async with token_lock:
        existing = set(globals.token_list)
        added = [token for token in tokens if token not in existing]
        globals.token_list.extend(added)
        _persist_tokens()
    return {"status": "ok", "added": len(added), "total": len(set(globals.token_list))}


@app.delete("/admin/api/credentials/{credential_id}", dependencies=[Depends(require_admin)])
async def admin_delete_credential(credential_id: str):
    async with token_lock:
        matches = [token for token in globals.token_list if _token_id(token) == credential_id]
        if not matches:
            raise HTTPException(status_code=404, detail="Credential not found")
        globals.token_list[:] = [token for token in globals.token_list if token not in matches]
        globals.error_token_list[:] = [token for token in globals.error_token_list if token not in matches]
        _persist_tokens()
    return {"status": "ok"}


@app.delete("/admin/api/errors", dependencies=[Depends(require_admin)])
async def admin_clear_errors():
    async with token_lock:
        globals.error_token_list.clear()
        _persist_tokens()
    return {"status": "ok"}


@app.get("/admin/api/models", dependencies=[Depends(require_admin)])
async def admin_models():
    if not configs.authorization_list:
        raise HTTPException(status_code=503, detail="AUTHORIZATION is not configured")
    catalog = await fetch_model_catalog(configs.authorization_list[0])
    response = to_openai_model_list(catalog)
    response["default_model"] = catalog.get("default_model_slug")
    response["model_picker_version"] = catalog.get("model_picker_version")
    return response
