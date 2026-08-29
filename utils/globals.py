import json
import os

import utils.configs as configs
from utils.Logger import logger

DATA_FOLDER = "data"
CREDENTIALS_FILE = os.path.join(DATA_FOLDER, "credentials.json")
WSS_MAP_FILE = os.path.join(DATA_FOLDER, "wss_map.json")
FP_FILE = os.path.join(DATA_FOLDER, "fp_map.json")
SEED_MAP_FILE = os.path.join(DATA_FOLDER, "seed_map.json")
CONVERSATION_MAP_FILE = os.path.join(DATA_FOLDER, "conversation_map.json")
MODEL_CATALOG_FILE = os.path.join(DATA_FOLDER, "model_catalog.json")

count = 0
credential_list = []
wss_map = {}
fp_map = {}
seed_map = {}
conversation_map = {}
impersonate_list = [
    "chrome99",
    "chrome100",
    "chrome101",
    "chrome104",
    "chrome107",
    "chrome110",
    "chrome116",
    "chrome119",
    "chrome120",
    "chrome123",
    "edge99",
    "edge101",
] if not configs.impersonate_list else configs.impersonate_list

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

if os.path.exists(CREDENTIALS_FILE):
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        try:
            stored_credentials = json.load(f)
            if isinstance(stored_credentials, dict):
                stored_credentials = stored_credentials.get("credentials", [])
            if isinstance(stored_credentials, list):
                credential_list = [item for item in stored_credentials if isinstance(item, dict)]
        except (OSError, ValueError):
            credential_list = []

if os.path.exists(WSS_MAP_FILE):
    with open(WSS_MAP_FILE, "r") as f:
        try:
            wss_map = json.load(f)
        except:
            wss_map = {}
else:
    wss_map = {}

if os.path.exists(FP_FILE):
    with open(FP_FILE, "r", encoding="utf-8") as f:
        try:
            fp_map = json.load(f)
        except:
            fp_map = {}
else:
    fp_map = {}

if os.path.exists(SEED_MAP_FILE):
    with open(SEED_MAP_FILE, "r") as f:
        try:
            seed_map = json.load(f)
        except:
            seed_map = {}
else:
    seed_map = {}

if os.path.exists(CONVERSATION_MAP_FILE):
    with open(CONVERSATION_MAP_FILE, "r") as f:
        try:
            conversation_map = json.load(f)
        except:
            conversation_map = {}
else:
    conversation_map = {}

if credential_list:
    error_count = sum(item.get("status") == "error" for item in credential_list)
    logger.info(f"Credential count: {len(credential_list)}, Error credential count: {error_count}")
    logger.info("-" * 60)
