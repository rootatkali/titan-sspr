"""Microsoft Graph API — user lookup and Teams OTP delivery."""
from __future__ import annotations

import logging
import time as _time
from typing import Any

import msal
import requests

logger = logging.getLogger(__name__)

# Module-level token cache (safe for single-process deployment)
_token_cache: dict[str, Any] = {}


def _get_config() -> dict:
    from flask import current_app
    return current_app.config


def get_access_token() -> str:
    """Return a valid access token, refreshing if needed."""
    cfg = _get_config()
    cache = _token_cache

    if cache.get("token") and _time.time() < cache.get("expires_at", 0) - 60:
        return cache["token"]

    authority = f"https://login.microsoftonline.com/{cfg['AZURE_TENANT_ID']}"
    app = msal.ConfidentialClientApplication(
        cfg["AZURE_CLIENT_ID"],
        authority=authority,
        client_credential=cfg["AZURE_CLIENT_SECRET"],
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(f"MSAL token acquisition failed: {result.get('error_description')}")

    cache["token"] = result["access_token"]
    cache["expires_at"] = _time.time() + result.get("expires_in", 3600)
    return cache["token"]


def lookup_user(username: str) -> dict | None:
    """
    Look up a user by sAMAccountName (which equals UPN prefix in this environment).
    Returns the Graph user object or None if not found.
    """
    cfg = _get_config()
    upn = f"{username}@{cfg['M365_DOMAIN']}"
    token = get_access_token()
    resp = requests.get(
        f"https://graph.microsoft.com/v1.0/users/{upn}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def send_otp_via_teams(user_id: str, otp: str) -> None:
    """
    Send the OTP to the user via a 1:1 Teams chat.
    Creates the chat if it doesn't exist (Graph handles idempotency).
    """
    cfg = _get_config()
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    bot_user_id = cfg["AZURE_BOT_USER_ID"]

    # Step 1: Create (or retrieve) 1:1 chat
    chat_payload = {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{bot_user_id}')",
            },
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')",
            },
        ],
    }
    resp = requests.post(
        "https://graph.microsoft.com/v1.0/chats",
        json=chat_payload,
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    chat_id = resp.json()["id"]

    # Step 2: Send message with OTP
    message_payload = {
        "body": {
            "contentType": "text",
            "content": (
                f"Your password reset code is: {otp}\n\n"
                "This code expires in 10 minutes. Do not share it with anyone."
            ),
        }
    }
    resp = requests.post(
        f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
        json=message_payload,
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    logger.info("OTP sent via Teams to user_id=%s", user_id)
