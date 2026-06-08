"""
Firebase Admin SDK client — lazy initialization.

Supports two credential modes:
  1. Service account JSON file (recommended for production):
       Set GOOGLE_APPLICATION_CREDENTIALS=./firebase-service-account.json
  2. Project-ID-only mode (no token verification, development/fallback):
       Set FIREBASE_PROJECT_ID=routemaster-os

The module NEVER crashes on import. Call `lazy_init()` before using
`firebase_admin.auth`.  It is safe to call multiple times.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("routemaster.firebase")

# --- module-level sentinel -------------------------------------------
_initialized: bool = False
_init_error: Optional[str] = None


def lazy_init() -> bool:
    """
    Initialize the Firebase Admin SDK exactly once.

    Returns True if the SDK is ready, False if it failed gracefully.
    Logs a warning (not an exception) on failure so the server still boots.
    """
    global _initialized, _init_error

    if _initialized:
        return True

    try:
        import firebase_admin  # noqa: F401
        from firebase_admin import credentials

        # Already initialized by another path?
        if firebase_admin._apps:
            _initialized = True
            logger.info("🔥 Firebase Admin SDK: already initialized.")
            return True

        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        firebase_project_id = os.getenv("FIREBASE_PROJECT_ID", "routemaster-os")

        if service_account_path and os.path.isfile(service_account_path):
            # Full service-account credentials — can verify ID tokens
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            logger.info(
                "🔥 Firebase Admin SDK initialized with service account: %s",
                service_account_path,
            )
        elif firebase_project_id:
            # Project-ID-only mode — limited: cannot verify ID tokens
            # (verify_id_token will raise unless Firebase sets up ADC)
            firebase_admin.initialize_app(options={"projectId": firebase_project_id})
            logger.warning(
                "⚠️  Firebase Admin SDK initialized with projectId ONLY (%s). "
                "ID-token verification will fail unless GOOGLE_APPLICATION_CREDENTIALS "
                "is set. Set it to ./firebase-service-account.json.",
                firebase_project_id,
            )
        else:
            # Application Default Credentials (ADC) — Cloud Run / GCP environments
            firebase_admin.initialize_app()
            logger.info("🔥 Firebase Admin SDK initialized via ADC (Cloud Run / GCP).")

        _initialized = True
        _init_error = None
        return True

    except Exception as exc:  # noqa: BLE001
        _init_error = str(exc)
        _initialized = False
        logger.error(
            "❌ Firebase Admin SDK failed to initialize: %s. "
            "Auth endpoints will not work until this is fixed. "
            "Generate a service account key at: "
            "https://console.firebase.google.com/project/routemaster-os"
            "/settings/serviceaccounts/adminsdk",
            exc,
        )
        return False


def is_ready() -> bool:
    """Return True if the SDK has been successfully initialized."""
    return _initialized


def get_auth():
    """
    Return the firebase_admin.auth module.
    Raises RuntimeError if the SDK was not initialized.
    """
    if not lazy_init():
        raise RuntimeError(
            "Firebase Admin SDK is not initialized. "
            "Check GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_PROJECT_ID in .env."
        )
    from firebase_admin import auth as _auth  # noqa: PLC0415

    return _auth


# -----------------------------------------------------------------------
# Attempt initialization on import (non-fatal).
# This warms up the SDK at startup so the first request doesn't pay the
# initialization cost.  If it fails the server keeps running.
# -----------------------------------------------------------------------
lazy_init()
