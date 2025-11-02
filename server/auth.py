# -*- coding: utf-8 -*-
"""
Google OAuth authentication
"""
from typing import Optional, Tuple
from google.auth.transport import requests
from google.oauth2 import id_token

from settings import GOOGLE_OAUTH_AUDIENCE


def verify_google_id_token(token: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Verify Google ID token and return (user_id, email)
    Returns (None, None) if verification fails
    """
    if not token or not GOOGLE_OAUTH_AUDIENCE:
        return None, None
    
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_OAUTH_AUDIENCE
        )
        
        # Extract user info
        user_id = idinfo.get("sub") or idinfo.get("email")
        email = idinfo.get("email")
        
        return user_id, email
    except Exception as e:
        # Token verification failed
        return None, None


def get_user_id_from_header(authorization: Optional[str]) -> str:
    """
    Extract user ID from Authorization header
    Returns 'anonymous' if not authenticated
    """
    if not authorization:
        return "anonymous"
    
    user_id, _ = verify_google_id_token(authorization)
    return user_id if user_id else "anonymous"
