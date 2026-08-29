import json
import random

from fastapi import HTTPException

import utils.configs as configs
import utils.globals as globals
from chatgpt.credentials import available_credentials, get_credential, refresh_all_credentials


def get_req_token(req_token, seed=None):
    credentials = available_credentials()
    if configs.auto_seed:
        if seed and credentials:
            if seed not in globals.seed_map:
                globals.seed_map[seed] = {"token": random.choice(credentials)["id"], "conversations": []}
                with open(globals.SEED_MAP_FILE, "w", encoding="utf-8") as file:
                    json.dump(globals.seed_map, file, indent=2)
            return globals.seed_map[seed]["token"]

        if req_token not in configs.authorization_list:
            raise HTTPException(status_code=401, detail="Invalid API key")
        if not credentials:
            raise HTTPException(status_code=503, detail="No active credentials")
        if configs.random_token:
            return random.choice(credentials)["id"]
        globals.count = (globals.count + 1) % len(credentials)
        return credentials[globals.count]["id"]

    if req_token not in globals.seed_map:
        raise HTTPException(status_code=401, detail={"error": "Invalid Seed"})
    return globals.seed_map[req_token]["token"]


async def verify_token(credential_id):
    credential = get_credential(credential_id)
    if not credential or credential.get("status") == "error":
        raise HTTPException(status_code=401, detail="Credential is unavailable")
    return credential["access_token"]


async def refresh_all_tokens(force_refresh=False):
    await refresh_all_credentials(force=force_refresh)
