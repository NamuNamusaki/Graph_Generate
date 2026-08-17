"""
Authentication for web_api/app_frontend.py.

SINGLE-USER SETUP
-----------------
There is exactly one account, and you define it in .env:

    APP_USERNAME=admin
    APP_PASSWORD=your-password-here
    APP_EMAIL=admin@smartbiopep.local

There is no public registration. On startup the API seeds that account into
the MySQL users table (see ensure_app_user()), hashing the password with
bcrypt first -- the plain password never reaches the database. Change
APP_PASSWORD in .env and restart the API and the stored hash is updated in
place; no manual SQL, no `docker compose down -v`.

A real users row is required (not just an env-var check) because
projects.user_id is a foreign key -- every submitted job has to belong to an
actual row in the users table.

What this module provides:

  1. Password hashing (bcrypt)

  2. Session tokens (use normal random secrets, not a fixed string)
  
  3. get_current_user() -- a FastAPI dependency
     Endpoints declare `current_user: dict = Depends(get_current_user)` and
     FastAPI runs this first: it reads the Authorization header, looks the
     token up, loads the user from MySQL, and hands the real user row to the
     endpoint. A request with a missing or unknown token never reaches the
     endpoint body at all.
"""
from __future__ import annotations

import os
import secrets
import time
from typing import Dict, Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import db

# -----------------------------------------------------------------------------------------
# CONFIGURATION -- the one account, defined in .env
# -----------------------------------------------------------------------------------------
APP_USERNAME = os.environ.get("APP_USERNAME", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
APP_EMAIL = os.environ.get("APP_EMAIL", "admin@smartbiopep.local")

if not APP_PASSWORD:
    # Fail loudly at import time rather than starting with no usable login.
    raise RuntimeError(
        "APP_PASSWORD environment variable is not set. Add the login "
        "credentials to your .env file:\n"
        "    APP_USERNAME=admin\n"
        "    APP_PASSWORD=choose-a-password\n"
        "    APP_EMAIL=admin@smartbiopep.local"
    )

# bcrypt hashes at most the first 72 BYTES of a password and silently ignores
# the rest, so anything longer would be misleading about what's checked.
MAX_PASSWORD_BYTES = 72
if len(APP_PASSWORD.encode("utf-8")) > MAX_PASSWORD_BYTES:
    raise RuntimeError(f"APP_PASSWORD must be at most {MAX_PASSWORD_BYTES} bytes long.")


# -----------------------------------------------------------------------------------------
# 1. PASSWORD HASHING
# -----------------------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    """
    Hashes a plain-text password for storage in users.password_hash.
    gensalt() generates a fresh random salt every call, so hashing the same
    password twice produces two different hashes
    """
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, password_hash: Optional[str]) -> bool:
    """
    Checks a submitted password against the stored hash. Returns False
    (never raises) when there's no hash stored or the stored value is
    corrupt, so a bad row can't be logged into and can't crash the endpoint.
    """
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False

# -----------------------------------------------------------------------------------------
# 2. SEEDING THE ONE ACCOUNT
# -----------------------------------------------------------------------------------------
def ensure_app_user(retries: int = 10, delay_seconds: float = 2.0) -> dict:
    """
    Makes sure the account from .env exists in MySQL, and that its stored
    hash matches the current APP_PASSWORD. Called once at API startup.

    Safe to run every boot:
      - user missing        -> created with a freshly hashed password
      - password changed    -> stored hash is updated
      - nothing changed     -> left alone (no pointless writes)
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            user = db.get_user_by_username(APP_USERNAME)

            if user is None:
                user_id = db.create_user(APP_USERNAME, APP_EMAIL, hash_password(APP_PASSWORD))
                print(f"[auth] Created application user '{APP_USERNAME}' (id={user_id}).")
                return db.get_user(user_id)

            # Existing row: refresh the hash only if the .env password no
            # longer matches what's stored.
            if not verify_password(APP_PASSWORD, user.get("password_hash")):
                db.update_user_password_hash(user["id"], hash_password(APP_PASSWORD))
                print(f"[auth] Updated password for application user '{APP_USERNAME}'.")
            else:
                print(f"[auth] Application user '{APP_USERNAME}' is up to date.")

            return db.get_user(user["id"])

        except Exception as exc:  # DB not reachable / schema not applied yet
            last_error = exc
            if attempt < retries:
                print(f"[auth] Database not ready ({exc}); retry {attempt}/{retries} in {delay_seconds}s...")
                time.sleep(delay_seconds)

    raise RuntimeError(f"Could not seed the application user after {retries} attempts: {last_error}")

# -----------------------------------------------------------------------------------------
# 3. SESSION TOKENS
# -----------------------------------------------------------------------------------------
# token string -> user id. In-memory only; see the tradeoffs in the module
# docstring above.
_active_tokens: Dict[str, int] = {}

def create_access_token(user_id: int) -> str:
    """
    Issues a new random session token for this user and remembers it.

    secrets.token_urlsafe() uses the OS cryptographic random source, so the
    token can't be guessed -- unlike the old fixed 'fake_mock_jwt_token'
    string, which was the same for everyone forever.
    """
    token = secrets.token_urlsafe(32)
    _active_tokens[token] = user_id
    return token

def revoke_access_token(token: str) -> None:
    """Forgets a token, so it stops working immediately (used by logout)."""
    _active_tokens.pop(token, None)

def authenticate_user(username: str, password: str) -> dict:
    """
    Checks a login attempt and returns the user row, or raises HTTP 401.

    The same message is returned whether the username or the password was
    wrong -- saying which one was correct would help an attacker guess.
    """
    user = db.get_user_by_username(username)
    if user is None or not verify_password(password, user.get("password_hash")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return user

# -----------------------------------------------------------------------------------------
# 4. THE FastAPI DEPENDENCY
# -----------------------------------------------------------------------------------------
# auto_error=False so a missing header reaches our own handler below and
# produces a consistent error shape, instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = _active_tokens.get(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is no longer valid. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Never let the hash leave this module.
    user.pop("password_hash", None)
    return user
