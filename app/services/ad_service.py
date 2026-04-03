"""Active Directory password reset via LDAPS."""
from __future__ import annotations

import logging
import ssl

from ldap3 import MODIFY_REPLACE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException

logger = logging.getLogger(__name__)


class ADError(Exception):
    """Raised when the AD operation fails."""


def _get_config() -> dict:
    from flask import current_app
    return current_app.config


def _build_server(cfg: dict) -> Server:
    tls = Tls(
        ca_certs_file=cfg["LDAP_CA_CERT_PATH"],
        validate=ssl.CERT_REQUIRED,
        version=ssl.PROTOCOL_TLS_CLIENT,
    )
    return Server(cfg["LDAP_SERVER"], port=cfg["LDAP_PORT"], use_ssl=True, tls=tls)


def _find_user_dn(conn: Connection, search_base: str, filter_template: str, username: str) -> str | None:
    search_filter = filter_template.replace("{username}", username)
    conn.search(search_base, search_filter, attributes=["distinguishedName"])
    if not conn.entries:
        return None
    return conn.entries[0].distinguishedName.value


def reset_password(username: str, new_password: str) -> None:
    """
    Reset the AD password for `username`.
    Raises ADError on failure.
    """
    cfg = _get_config()
    server = _build_server(cfg)
    conn = Connection(
        server,
        user=cfg["LDAP_SERVICE_ACCOUNT_DN"],
        password=cfg["LDAP_SERVICE_ACCOUNT_PASS"],
        auto_bind=True,
    )
    try:
        dn = _find_user_dn(
            conn,
            cfg["LDAP_SEARCH_BASE"],
            cfg["LDAP_USER_SEARCH_FILTER"],
            username,
        )
        if not dn:
            raise ADError(f"User '{username}' not found in directory")

        success = conn.extend.microsoft.modify_password(dn, new_password)
        if not success:
            raise ADError(f"modify_password returned failure for '{username}': {conn.result}")

        logger.info("Password reset successful for username=%s", username)
    except LDAPException as exc:
        raise ADError(f"LDAP error during password reset: {exc}") from exc
    finally:
        try:
            conn.unbind()
        except Exception:
            pass
