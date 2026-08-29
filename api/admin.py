import hashlib
import hmac
import time

from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse

import utils.configs as configs
import utils.globals as globals
from app import app
from chatgpt.credentials import (
    clear_credential_errors,
    delete_credential,
    refresh_credential,
    session_payload,
    upsert_credential,
)
from chatgpt.modelCatalog import get_model_catalog, to_openai_model_list


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
