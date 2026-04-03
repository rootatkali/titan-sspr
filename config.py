"""
Application configuration — loaded once at startup.
Raises RuntimeError immediately if required env vars are missing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_REQUIRED = [
    "SECRET_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_VERIFY_SERVICE_SID",
    "LDAP_SERVER",
    "LDAP_CA_CERT_PATH",
    "LDAP_SERVICE_ACCOUNT_DN",
    "LDAP_SERVICE_ACCOUNT_PASS",
    "LDAP_SEARCH_BASE",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD_HASH",
]


def _check_required() -> None:
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables:\n"
            + "\n".join(f"  - {k}" for k in missing)
        )


@dataclass(frozen=True)
class Config:
    # Flask core
    SECRET_KEY: str
    FLASK_ENV: str
    DEBUG: bool

    # Sessions
    SESSION_TYPE: str
    SESSION_FILE_DIR: str
    SESSION_PERMANENT: bool

    # Rate limiting
    RATELIMIT_OTP_SEND: str
    RATELIMIT_STORAGE_URI: str

    # Twilio Verify
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_VERIFY_SERVICE_SID: str

    # LDAP
    LDAP_SERVER: str
    LDAP_PORT: int
    LDAP_CA_CERT_PATH: str
    LDAP_SERVICE_ACCOUNT_DN: str
    LDAP_SERVICE_ACCOUNT_PASS: str
    LDAP_SEARCH_BASE: str
    LDAP_USER_SEARCH_FILTER: str

    # Admin
    ADMIN_USERNAME: str
    ADMIN_PASSWORD_HASH: str

    # Database
    SQLALCHEMY_DATABASE_URI: str
    SQLALCHEMY_TRACK_MODIFICATIONS: bool

    # Server
    HOST: str
    PORT: int

    @classmethod
    def from_env(cls) -> "Config":
        _check_required()
        flask_env = os.getenv("FLASK_ENV", "production")
        return cls(
            SECRET_KEY=os.environ["SECRET_KEY"],
            FLASK_ENV=flask_env,
            DEBUG=flask_env == "development",
            SESSION_TYPE=os.getenv("SESSION_TYPE", "filesystem"),
            SESSION_FILE_DIR=os.getenv("SESSION_FILE_DIR", "flask_session"),
            SESSION_PERMANENT=os.getenv("SESSION_PERMANENT", "false").lower() == "true",
            RATELIMIT_OTP_SEND=os.getenv("RATELIMIT_OTP_SEND", "5 per hour"),
            RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
            TWILIO_ACCOUNT_SID=os.environ["TWILIO_ACCOUNT_SID"],
            TWILIO_AUTH_TOKEN=os.environ["TWILIO_AUTH_TOKEN"],
            TWILIO_VERIFY_SERVICE_SID=os.environ["TWILIO_VERIFY_SERVICE_SID"],
            LDAP_SERVER=os.environ["LDAP_SERVER"],
            LDAP_PORT=int(os.getenv("LDAP_PORT", "636")),
            LDAP_CA_CERT_PATH=os.environ["LDAP_CA_CERT_PATH"],
            LDAP_SERVICE_ACCOUNT_DN=os.environ["LDAP_SERVICE_ACCOUNT_DN"],
            LDAP_SERVICE_ACCOUNT_PASS=os.environ["LDAP_SERVICE_ACCOUNT_PASS"],
            LDAP_SEARCH_BASE=os.environ["LDAP_SEARCH_BASE"],
            LDAP_USER_SEARCH_FILTER=os.getenv(
                "LDAP_USER_SEARCH_FILTER", "(sAMAccountName={username})"
            ),
            ADMIN_USERNAME=os.environ["ADMIN_USERNAME"],
            ADMIN_PASSWORD_HASH=os.environ["ADMIN_PASSWORD_HASH"],
            SQLALCHEMY_DATABASE_URI=os.getenv(
                "SQLALCHEMY_DATABASE_URI", "sqlite:///data/audit.db"
            ),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            HOST=os.getenv("HOST", "0.0.0.0"),
            PORT=int(os.getenv("PORT", "8080")),
        )
