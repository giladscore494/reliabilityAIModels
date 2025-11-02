# -*- coding: utf-8 -*-
"""
Settings and environment configuration
"""
import os
import json
from typing import Optional

# Server settings
PORT = int(os.getenv("PORT", "8000"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Google Sheets
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Auth (Google OAuth)
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_AUDIENCE = os.getenv("GOOGLE_OAUTH_AUDIENCE", "")

# Rate Limits
GLOBAL_DAILY_LIMIT = int(os.getenv("GLOBAL_DAILY_LIMIT", "1000"))
USER_DAILY_LIMIT = int(os.getenv("USER_DAILY_LIMIT", "5"))
CACHE_MAX_DAYS = int(os.getenv("CACHE_MAX_DAYS", "45"))

# PostgreSQL (optional)
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

# Model configuration
PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-1.5-flash-latest"
RETRIES = 2
RETRY_BACKOFF_SEC = 1.5

# Headers for Google Sheets
REQUIRED_HEADERS = [
    "date", "user_id", "make", "model", "sub_model", "year", "fuel", "transmission",
    "mileage_range", "base_score_calculated", "score_breakdown", "avg_cost",
    "issues", "search_performed", "reliability_summary", "issues_with_costs",
    "sources", "recommended_checks", "common_competitors_brief"
]

def get_service_account_dict():
    """Parse and return service account JSON"""
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        return None
    try:
        svc = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        # Fix newlines in private key
        if "\\n" in svc.get("private_key", ""):
            svc["private_key"] = svc["private_key"].replace("\\n", "\n")
        return svc
    except Exception:
        return None
