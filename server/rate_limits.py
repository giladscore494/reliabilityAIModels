# -*- coding: utf-8 -*-
"""
Rate limiting logic for global and per-user quotas
"""
import datetime
import pandas as pd
from typing import Tuple

from settings import GLOBAL_DAILY_LIMIT, USER_DAILY_LIMIT, DATABASE_URL
from sheets_layer import sheet_to_df


def within_daily_global_limit(df: pd.DataFrame, limit: int = GLOBAL_DAILY_LIMIT) -> Tuple[bool, int]:
    """
    Check if within daily global limit
    Returns (within_limit, count_today)
    """
    today = datetime.date.today().isoformat()
    
    if df.empty or "date" not in df.columns:
        return True, 0
    
    try:
        cnt = len(df[df["date"].astype(str) == today])
    except Exception:
        cnt = 0
    
    return (cnt < limit), cnt


def within_user_daily_limit(user_id: str, df: pd.DataFrame, limit: int = USER_DAILY_LIMIT) -> Tuple[bool, int]:
    """
    Check if user is within daily limit
    Returns (within_limit, count_today)
    """
    today = datetime.date.today().isoformat()
    
    if df.empty or "date" not in df.columns or "user_id" not in df.columns:
        return True, 0
    
    try:
        user_today = df[
            (df["date"].astype(str) == today) & 
            (df["user_id"].astype(str) == user_id)
        ]
        cnt = len(user_today)
    except Exception:
        cnt = 0
    
    return (cnt < limit), cnt


def check_rate_limits(user_id: str) -> Tuple[bool, int, int]:
    """
    Check both global and user rate limits
    Returns (can_proceed, user_count, global_count)
    """
    df = sheet_to_df()
    
    # Check global limit
    global_ok, global_cnt = within_daily_global_limit(df)
    if not global_ok:
        return False, 0, global_cnt
    
    # Check user limit
    user_ok, user_cnt = within_user_daily_limit(user_id, df)
    if not user_ok:
        return False, user_cnt, global_cnt
    
    return True, user_cnt, global_cnt


def get_remaining_quota(user_id: str) -> Tuple[int, int]:
    """
    Get remaining quota for user and globally
    Returns (user_left, global_left)
    """
    df = sheet_to_df()
    
    _, global_cnt = within_daily_global_limit(df)
    _, user_cnt = within_user_daily_limit(user_id, df)
    
    user_left = max(0, USER_DAILY_LIMIT - user_cnt)
    global_left = max(0, GLOBAL_DAILY_LIMIT - global_cnt)
    
    return user_left, global_left
