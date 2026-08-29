import asyncio
import base64
import hashlib
import json
import os
import random
import time
from urllib.parse import unquote

from fastapi import HTTPException

import utils.configs as configs
import utils.globals as globals
from utils.Client import Client
from utils.Logger import logger


SESSION_COOKIE_NAME = "__Secure-next-auth.session-token"
SESSION_COOKIE_CHUNK_SIZE = 3933
credential_lock = asyncio.Lock()
refresh_locks = {}


def _credential_id(account_id):
    return hashlib.sha256(account_id.encode()).hexdigest()[:16]


def _clean_token(value):
    token = str(value or "").strip().strip("\"'").replace("\r", "").replace("\n", "")
    prefix = f"{SESSION_COOKIE_NAME}="
    if token.startswith(prefix):
        token = token[len(prefix):]
    if ";" in token:
        token = token.split(";", 1)[0]
    return unquote(token.strip())


def _jwt_expiry(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def parse_session_json(content):
    try:
        payload = json.loads(content) if isinstance(content, str) else content
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Credential must be a complete Session JSON object")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Credential must be a complete Session JSON object")

    access_token = _clean_token(payload.get("accessToken") or payload.get("access_token"))
    session_token = _clean_token(payload.get("sessionToken") or payload.get("session_token"))
    account = payload.get("account") if isinstance(payload.get("account"), dict) else {}
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    account_id = str(account.get("id") or "").strip()
    email = str(user.get("email") or "").strip() or None

    missing = []
    if not access_token:
        missing.append("accessToken")
    if not session_token:
        missing.append("sessionToken")
    if not account_id:
        missing.append("account.id")
    if missing:
        raise HTTPException(status_code=400, detail=f"Session JSON is missing: {', '.join(missing)}")

    now = int(time.time())
    return {
        "id": _credential_id(account_id),
        "access_token": access_token,
        "session_token": session_token,
        "account_id": account_id,
        "email": email,
        "access_expires_at": _jwt_expiry(access_token),
        "updated_at": now,
        "status": "active",
        "last_error": None,
    }


def get_credential(credential_id):
    return next((item for item in globals.credential_list if item.get("id") == credential_id), None)


def available_credentials():
    return [item for item in globals.credential_list if item.get("status") != "error"]


def is_expired_error(error):
    detail = str(getattr(error, "detail", error)).lower()
    return getattr(error, "status_code", None) == 401 or any(
        marker in detail
        for marker in ("token_expired", "token expired", "access token has expired", "jwt expired")
    )


def _persist_credentials():
    temp_file = globals.CREDENTIALS_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump({"version": 1, "credentials": globals.credential_list}, file, ensure_ascii=False, indent=2)
    os.chmod(temp_file, 0o600)
    os.replace(temp_file, globals.CREDENTIALS_FILE)


def session_payload(credential):
    payload = {
        "accessToken": credential["access_token"],
        "sessionToken": credential["session_token"],
        "account": {"id": credential["account_id"]},
    }
    if credential.get("email"):
        payload["user"] = {"email": credential["email"]}
    return payload


async def upsert_credential(content):
    credential = parse_session_json(content)
    async with credential_lock:
        existing = get_credential(credential["id"])
        if existing:
            existing.update(credential)
            created = False
        else:
            globals.credential_list.append(credential)
            created = True
        _persist_credentials()
    return credential, created


async def delete_credential(credential_id):
    async with credential_lock:
        original_count = len(globals.credential_list)
        globals.credential_list[:] = [item for item in globals.credential_list if item.get("id") != credential_id]
        if len(globals.credential_list) == original_count:
            raise HTTPException(status_code=404, detail="Credential not found")
        _persist_credentials()


async def clear_credential_errors():
    async with credential_lock:
        for credential in globals.credential_list:
            credential["status"] = "active"
            credential["last_error"] = None
        _persist_credentials()


def _session_cookie_header(token):
    if len(token) <= SESSION_COOKIE_CHUNK_SIZE:
        return f"{SESSION_COOKIE_NAME}={token}"
    return "; ".join(
        f"{SESSION_COOKIE_NAME}.{index}={token[offset:offset + SESSION_COOKIE_CHUNK_SIZE]}"
        for index, offset in enumerate(range(0, len(token), SESSION_COOKIE_CHUNK_SIZE))
    )


def _session_token_from_cookies(cookies, fallback):
    jar = getattr(cookies, "jar", None)
    if jar is None:
        return fallback
    exact = None
    chunks = {}
    for cookie in jar:
        if cookie.name == SESSION_COOKIE_NAME and cookie.value:
            exact = _clean_token(cookie.value)
        elif cookie.name.startswith(f"{SESSION_COOKIE_NAME}.") and cookie.value:
            suffix = cookie.name.rsplit(".", 1)[-1]
            if suffix.isdigit():
                chunks[int(suffix)] = _clean_token(cookie.value)
    if exact:
        return exact
    if chunks and set(chunks) == set(range(max(chunks) + 1)):
        return "".join(chunks[index] for index in range(max(chunks) + 1))
    return fallback


async def refresh_credential(credential_id, force=True):
    lock = refresh_locks.setdefault(credential_id, asyncio.Lock())
    async with lock:
        credential = get_credential(credential_id)
        if not credential:
            raise HTTPException(status_code=401, detail="Credential not found")
        if not force and credential.get("access_expires_at", 0) > int(time.time()) + 300:
            return credential

        proxy = random.choice(configs.proxy_url_list) if configs.proxy_url_list else None
        client = Client(proxy=proxy, impersonate="chrome")
        current_session = credential["session_token"]
        response = None
        session_data = None
        requests = [
            {
                "params": {"refresh": "true", "reason": "token_expired", "method": "POST", "path": "/ces/v1/rgstr"},
                "headers": {"referer": "https://chatgpt.com/"},
            },
            {},
        ] if force else [{}]
        try:
            for request_options in requests:
                headers = {
                    "accept": "application/json",
                    "cookie": _session_cookie_header(current_session),
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
                    **request_options.get("headers", {}),
                }
                response = await client.get(
                    "https://chatgpt.com/api/auth/session",
                    headers=headers,
                    params=request_options.get("params"),
                    timeout=45,
                )
                current_session = _session_token_from_cookies(response.cookies, current_session)
                current_session = _session_token_from_cookies(client.session.cookies, current_session)
                if response.status_code == 200:
                    candidate = response.json()
                    if isinstance(candidate, dict) and candidate.get("accessToken"):
                        session_data = candidate
            if session_data is None:
                detail = f"Session refresh failed with HTTP {response.status_code if response else 502}"
                raise HTTPException(status_code=401, detail=detail)

            refreshed = parse_session_json({**session_data, "sessionToken": current_session})
            if refreshed["account_id"] != credential["account_id"]:
                raise HTTPException(status_code=409, detail="Refreshed Session belongs to a different account")
            refreshed["id"] = credential_id
            async with credential_lock:
                credential.update(refreshed)
                _persist_credentials()
            logger.info(f"Credential {credential_id[:12]} refreshed")
            return credential
        except HTTPException as error:
            async with credential_lock:
                credential["status"] = "error"
                credential["last_error"] = str(error.detail)[:200]
                credential["updated_at"] = int(time.time())
                _persist_credentials()
            raise
        finally:
            await client.close()


async def refresh_all_credentials(force=False):
    for credential in list(available_credentials()):
        try:
            await refresh_credential(credential["id"], force=force)
        except HTTPException:
            pass
