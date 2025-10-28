# -*- coding: utf-8 -*-
"""
Cache lookup and similarity matching
"""
import re
import json
import difflib
import pandas as pd
from typing import Optional, Tuple, Any, Dict

from settings import CACHE_MAX_DAYS
from sheets_layer import sheet_to_df


def normalize_text(s: Any) -> str:
    """Normalize text for comparison"""
    if s is None:
        return ""
    s = re.sub(r"\(.*?\)", " ", str(s))
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings"""
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def mileage_is_close(requested: str, stored: str, thr: float = 0.92) -> bool:
    """Check if mileage ranges are similar"""
    if requested is None or stored is None:
        return False
    return similarity(str(requested), str(stored)) >= thr


def safe_json_parse(value: Any, default=None):
    """Safely parse JSON value"""
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    s = str(value)
    if not s.strip():
        return default
    try:
        return json.loads(s)
    except Exception:
        try:
            from json_repair import repair_json
            fixed = repair_json(s)
            return json.loads(fixed)
        except Exception:
            return default


def parse_year_range_from_model_label(model_label: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract year range from model label like 'Model (2003-2025)'"""
    m = re.search(r"\((\d{4})\s*-\s*(\d{4})\)", str(model_label))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def match_hits_core(recent: pd.DataFrame, year: int, make: str, model: str, 
                    sub_model: Optional[str], th: float) -> pd.DataFrame:
    """Core matching logic for cache hits"""
    mk, md, sm = normalize_text(make), normalize_text(model), normalize_text(sub_model or "")
    use_sub = len(sm) > 0
    
    cand = recent[
        (pd.to_numeric(recent["year"], errors="coerce").astype("Int64") == int(year)) &
        (recent["make"].apply(lambda x: similarity(x, mk) >= th)) &
        (recent["model"].apply(lambda x: similarity(x, md) >= th))
    ]
    
    if use_sub and "sub_model" in recent.columns:
        cand = cand[cand["sub_model"].apply(lambda x: similarity(x, sm) >= th)]
    
    if "date" in cand.columns:
        try:
            cand["date"] = pd.to_datetime(cand["date"], errors="coerce")
            cand = cand.sort_values("date")
        except Exception:
            pass
    
    return cand


def get_cached_from_sheet(make: str, model: str, sub_model: str, year: int, 
                         mileage_range: str, max_days: int = CACHE_MAX_DAYS) -> Tuple[Optional[dict], pd.DataFrame, bool, bool]:
    """
    Search for cached results in Google Sheet
    Returns: (parsed_row, df, used_fallback, mileage_matched)
    """
    df = sheet_to_df()
    
    if df.empty:
        return None, df, False, False
    
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    except Exception:
        pass
    
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=max_days)
    recent = df[df["date"] >= cutoff] if "date" in df.columns else df
    
    used_fallback = False
    mileage_matched = False
    
    # Try matching with sub_model
    hits = pd.DataFrame()
    for th in (0.97, 0.93):
        hits = match_hits_core(recent, year, make, model, sub_model, th)
        if not hits.empty:
            break
    
    # Fallback without sub_model
    if hits.empty and sub_model:
        used_fallback = True
        for th in (0.97, 0.93):
            hits = match_hits_core(recent, year, make, model, None, th)
            if not hits.empty:
                break
    
    if hits.empty:
        return None, df, used_fallback, mileage_matched
    
    req_mil = str(mileage_range or "")
    
    def row_mil_sim(row):
        stored = str(row.get("mileage_range", "") or "")
        return similarity(req_mil, stored)
    
    hits = hits.copy()
    hits["__mil_sim"] = hits.apply(row_mil_sim, axis=1)
    hits = hits.sort_values(["__mil_sim", "date"], ascending=[False, False])
    
    best = hits.iloc[0]
    mileage_matched = mileage_is_close(req_mil, best.get("mileage_range", ""))
    
    def row_to_parsed(r: dict):
        score_breakdown = safe_json_parse(r.get("score_breakdown"), {}) or {}
        issues_with_costs = safe_json_parse(r.get("issues_with_costs"), []) or []
        recommended_checks = safe_json_parse(r.get("recommended_checks"), []) or []
        competitors = safe_json_parse(r.get("common_competitors_brief"), []) or []
        sources = safe_json_parse(r.get("sources"), []) or r.get("sources", "")
        
        base_calc = r.get("base_score_calculated")
        if base_calc in [None, "", "nan"]:
            legacy_base = r.get("base_score")
            try:
                base_calc = int(round(float(legacy_base)))
            except Exception:
                base_calc = None
        
        issues_raw = r.get("issues", [])
        if isinstance(issues_raw, str) and issues_raw:
            if ";" in issues_raw:
                issues_list = [x.strip() for x in issues_raw.split(";") if x.strip()]
            elif "," in issues_raw:
                issues_list = [x.strip() for x in issues_raw.split(",") if x.strip()]
            else:
                issues_list = [issues_raw.strip()]
        elif isinstance(issues_raw, list):
            issues_list = [str(x).strip() for x in issues_raw if str(x).strip()]
        else:
            issues_list = []
        
        last_dt = r.get("date")
        last_date_str = ""
        if isinstance(last_dt, pd.Timestamp):
            last_date_str = str(last_dt.date())
        elif last_dt:
            last_date_str = str(last_dt)[:10]
        
        return {
            "score_breakdown": score_breakdown,
            "base_score_calculated": base_calc,
            "common_issues": issues_list,
            "avg_repair_cost_ILS": r.get("avg_cost"),
            "issues_with_costs": issues_with_costs,
            "reliability_summary": r.get("reliability_summary") or "",
            "sources": sources if isinstance(sources, list) else [sources] if sources else [],
            "recommended_checks": recommended_checks,
            "common_competitors_brief": competitors,
            "last_date": last_date_str,
            "cached_mileage_range": r.get("mileage_range", "")
        }
    
    parsed_row = row_to_parsed(best.to_dict())
    parsed_row["is_aggregate"] = False
    parsed_row["count"] = int(len(hits))
    
    return parsed_row, df, used_fallback, mileage_matched
