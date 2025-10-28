# -*- coding: utf-8 -*-
"""
AI model logic - prompt building, model calling, mileage adjustments
"""
import re
import json
import time
from typing import Tuple, Optional, Dict, Any
import google.generativeai as genai
from json_repair import repair_json

from settings import (
    GEMINI_API_KEY,
    PRIMARY_MODEL,
    FALLBACK_MODEL,
    RETRIES,
    RETRY_BACKOFF_SEC
)


# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def build_prompt(make: str, model: str, sub_model: Optional[str], year: int,
                 fuel_type: str, transmission: str, mileage_range: str) -> str:
    """Build prompt for AI model"""
    extra = f" תת-דגם/תצורה: {sub_model}" if sub_model else ""
    
    return f"""
אתה מומחה לאמינות רכבים בישראל עם גישה לחיפוש אינטרנטי.
הניתוח חייב להתייחס ספציפית לטווח הקילומטראז' הנתון.
החזר JSON בלבד:

{{
  "search_performed": true,
  "score_breakdown": {{
    "engine_transmission_score": "מספר (1-10)",
    "electrical_score": "מספר (1-10)",
    "suspension_brakes_score": "מספר (1-10)",
    "maintenance_cost_score": "מספר (1-10)",
    "satisfaction_score": "מספר (1-10)",
    "recalls_score": "מספר (1-10)"
  }},
  "base_score_calculated": "מספר (0-100)",
  "common_issues": ["תקלות נפוצות רלוונטיות לק\\"מ"],
  "avg_repair_cost_ILS": "מספר ממוצע",
  "issues_with_costs": [
    {{"issue": "שם התקלה", "avg_cost_ILS": "מספר", "source": "מקור", "severity": "נמוך/בינוני/גבוה"}}
  ],
  "reliability_summary": "סיכום בעברית",
  "sources": ["רשימת אתרים"],
  "recommended_checks": ["בדיקות מומלצות ספציפיות"],
  "common_competitors_brief": [
      {{"model": "שם מתחרה 1", "brief_summary": "אמינות בקצרה"}},
      {{"model": "שם מתחרה 2", "brief_summary": "אמינות בקצרה"}}
  ]
}}

רכב: {make} {model}{extra} {int(year)}
טווח קילומטראז': {mileage_range}
סוג דלק: {fuel_type}
תיבת הילוכים: {transmission}
כתוב בעברית בלבד.
""".strip()


def call_model_with_retry(prompt: str) -> dict:
    """
    Call AI model with retry logic
    Tries PRIMARY_MODEL first, then FALLBACK_MODEL
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")
    
    last_err = None
    
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        try:
            llm = genai.GenerativeModel(model_name)
        except Exception as e:
            last_err = e
            continue
        
        for attempt in range(1, RETRIES + 1):
            try:
                resp = llm.generate_content(prompt)
                raw = (getattr(resp, "text", "") or "").strip()
                
                # Try to extract JSON
                try:
                    m = re.search(r"\{.*\}", raw, re.DOTALL)
                    data = json.loads(m.group()) if m else json.loads(raw)
                except Exception:
                    data = json.loads(repair_json(raw))
                
                return data
            except Exception as e:
                last_err = e
                if attempt < RETRIES:
                    time.sleep(RETRY_BACKOFF_SEC)
                continue
    
    raise RuntimeError(f"Model failed after all retries: {repr(last_err)}")


def normalize_mileage_text(mileage_range: str) -> str:
    """Normalize mileage text for comparison"""
    return re.sub(r"\s+", " ", str(mileage_range or "")).strip().lower()


def mileage_adjustment(mileage_range: str) -> Tuple[int, Optional[str]]:
    """
    Calculate score adjustment based on mileage
    Returns (delta, note)
    """
    m = normalize_mileage_text(mileage_range)
    
    if not m:
        return 0, None
    
    if "200" in m and "+" in m:
        return -15, "הציון הותאם מטה עקב קילומטראז׳ גבוה מאוד (200K+)."
    
    if "150" in m and "200" in m:
        return -10, "הציון הותאם מטה עקב קילומטראז׳ גבוה (150–200 אלף ק״מ)."
    
    if "100" in m and "150" in m:
        return -5, "הציון הותאם מעט מטה עקב קילומטראז׳ בינוני-גבוה (100–150 אלף ק״מ)."
    
    return 0, None


def apply_mileage_logic(result_obj: dict, requested_mileage: str) -> Tuple[dict, Optional[str]]:
    """
    Apply mileage adjustment to result object
    Returns (updated_result, note)
    """
    delta, note = mileage_adjustment(requested_mileage)
    
    if delta != 0:
        try:
            base = int(result_obj.get("base_score_calculated") or 0)
        except Exception:
            base = 0
        
        new_base = max(0, min(100, base + delta))
        result_obj["base_score_calculated"] = new_base
    
    return result_obj, note
