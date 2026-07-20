"""Google OAuth 2.0 (Authorization Code + PKCE).

``start()`` builds the consent URL with an S256 ``code_challenge`` and a random
``state`` (both echoed back and validated on callback). ``complete()`` exchanges
the code for tokens, fetches userinfo, and requires a **verified** email. All
HTTP goes through an injected ``httpx.AsyncClient`` so tests can mock Google.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


class OAuthError(Exception):
    pass


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class GoogleOAuthService:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http = http

    def start(self) -> tuple[str, str, str]:
        """Return ``(auth_url, state, code_verifier)``."""
        state = secrets.token_urlsafe(24)
        verifier, challenge = _pkce_pair()
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{AUTH_ENDPOINT}?{urlencode(params)}", state, verifier

    async def complete(self, code: str, code_verifier: str) -> dict[str, Any]:
        """Exchange the code, fetch userinfo, and return a normalized profile."""
        token_resp = await self._http.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
        if token_resp.status_code != 200:
            raise OAuthError("token exchange failed")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise OAuthError("no access token in token response")

        info_resp = await self._http.get(
            USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}
        )
        if info_resp.status_code != 200:
            raise OAuthError("userinfo request failed")
        info = info_resp.json()
        if not info.get("email") or not info.get("email_verified"):
            raise OAuthError("google account has no verified email")
        return {
            "sub": str(info["sub"]),
            "email": str(info["email"]).strip().lower(),
            "name": info.get("name") or info["email"],
        }
