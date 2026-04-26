from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from firebase_config import auth, require_firebase_app


router = APIRouter()
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Firebase ID token.",
        )

    try:
        require_firebase_app()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured on the backend.",
        ) from exc

    try:
        decoded = auth.verify_id_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token.",
        ) from exc

    provider = decoded.get("firebase", {}).get("sign_in_provider")
    return {
        "uid": decoded.get("uid"),
        "email": decoded.get("email"),
        "name": decoded.get("name"),
        "provider": provider,
        "is_guest": provider == "anonymous",
    }


@router.post("/verify")
def verify_token(current_user: dict[str, Any] = Depends(get_current_user)):
    return current_user


@router.get("/me")
def me(current_user: dict[str, Any] = Depends(get_current_user)):
    return current_user
