# -*- coding: utf-8 -*-
# ===========================================================
# 🚗 Car Reliability Analyzer – Israel (v3.9.0 • Pro UX Clean)
# Sheets + 45d Cache • No auth/signup • Soft 30-char indicator (no blocking)
# Free-text sub-model always allowed • A→B fallback (sub-model -> model-only)
# Mileage: flexible match + explicit warning • Score penalty by km-range
# Modern UI: "Advanced Mode — Free Input" toggle • No debug prints
# ===========================================================

import json, re, time, datetime, difflib, traceback
from typing import Optional, Tuple, Any, Dict, List

import pandas as pd
import streamlit as st
from json_repair import repair_json
import google.generativeai as genai

# =========================
# ========= CONFIG ========
# =========================
PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-1.5-flash-latest"
RETRIES = 2
RETRY_BACKOFF_SEC = 1.5

SOFT_MAX_LEN = 30            # מציגים מונה/אזהרה בלבד, לא חוסמים
GLOBAL_DAILY_LIMIT = 1000    # מגבלת בקשות גלובלית (ללא זיהוי משתמש)

st.set_page_config(page_title="🚗 Car Reliability Analyzer (Sheets)", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# =========================
# ======== Secrets ========
# =========================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

if not GEMINI_API_KEY:
    st.error("חסר GEMINI_API_KEY ב-Secrets.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)

# =========================
# === Models dictionary ===
# =========================
# צפה שקובץ זה קיים. אחרת, צור אותו עם מילון {'Make': ['Model (yyyy-yyyy)', ...], ...}
try:
    from car_models_dict import israeli_car_market_full_compilation
except Exception:
    israeli_car_market_full_compilation = {
        "Volkswagen": [
            "Golf (2004-2025)",
            "Polo (2005-2025)",
            "Passat (2005-2025)",
            "Scirocco (2008-2017)"  # דוגמה; אפשר להרחיב
        ],
        "Toyota": [
            "Corolla (2008-2025)",
            "Yaris (2008-2025)",
            "CHR (2016-2025)"
        ],
    }

# =========================
# ===== Helper funcs ======
# =========================
def normalize_text(s: Any) -> str:
    if s is None:
        return ""
    s = re.sub(r"\(.*?\)", " ", str(s))
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def parse_year_range_from_model_label(model_label: str) -> Tuple[Optional[int], Optional[int]]:
    m = re.search(r"\((\d{4})\s*-\s*(\d{4})", str(model_label))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)

def safe_json_parse(value: Any, default=None):
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    s = str(value).strip()
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        try:
            fixed = repair_json(s)
            return json.loads(fixed)
        except Exception:
            return default

def char_counter(label: str, value: str, soft_max: int = SOFT_MAX_LEN):
    """מציג מונה תווים + אזהרה רכה אם עברנו soft_max (ללא חסימה)."""
    ln = len(value or "")
    st.caption(f"{label} — {ln} תווים" + (f" (מומלץ עד {soft_max})" if ln > soft_max else ""))

# =========================
# ===== Sheets Layer ======
# =========================
REQUIRED_HEADERS = [
    "date","user_id","make","model","sub_model","year","fuel","transmission",
    "mileage_range",
    "base_score_calculated","score_breakdown","avg_cost","issues","search_performed",
    "reliability_summary","issues_with_costs","sources",
    "recommended_checks","common_competitors_brief"
]

def connect_sheet():
    if not (GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON):
        st.error("אין חיבור למאגר (Secrets חסרים).")
        st.stop()
    try:
        svc = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        if "\\n" in svc.get("private_key", ""):
            svc["private_key"] = svc["private_key"].replace("\\n", "\n")
        from google.oauth2.service_account import Credentials
        import gspread
        credentials = Credentials.from_service_account_info(
            svc, scopes=["https://www.googleapis.com/auth/spreadsheets",
                         "https://www.googleapis.com/auth/drive"]
        )
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        ws = sh.sheet1

        current = ws.row_values(1)
        if [c.lower() for c in current] != REQUIRED_HEADERS:
            ws.update("A1", [REQUIRED_HEADERS], value_input_option="USER_ENTERED")
        return ws
    except Exception as e:
        st.error("אין חיבור למאגר (שיתוף/הרשאות/Sheet).")
        st.code(repr(e))
        st.stop()

ws = connect_sheet()

def sheet_to_df() -> pd.DataFrame:
    try:
        recs = ws.get_all_records()
        df = pd.DataFrame(recs) if recs else pd.DataFrame(columns=REQUIRED_HEADERS)
    except Exception as e:
        st.error("כשל בקריאת המאגר.")
        st.code(repr(e))
        return pd.DataFrame(columns=REQUIRED_HEADERS)

    for h in REQUIRED_HEADERS:
        if h not in df.columns:
            df[h] = ""
    return df

def append_row_to_sheet(row_dict: dict):
    row = [row_dict.get(k, "") for k in REQUIRED_HEADERS]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error("כשל בכתיבה למאגר.")
        st.code(repr(e))

# =========================
# ===== Limits/Quota ======
# =========================
def within_daily_global_limit(df: pd.DataFrame, limit=GLOBAL_DAILY_LIMIT):
    today = datetime.date.today().isoformat()
    if df.empty or "date" not in df.columns:
        return True, 0
    cnt = len(df[df["date"].astype(str) == today])
    return (cnt < limit, cnt)

# =========================
# ==== Mileage logic  =====
# =========================
def mileage_adjustment(mileage_range: str):
    """
    מחזיר (delta, note) כאשר delta מצורף לציון המשוקלל (שלילי לרוב),
    ו-note הוא טקסט הסבר בעברית להצגה למשתמש.
    """
    m = normalize_text(mileage_range or "")
    if not m:
        return 0, None
    if "200" in m and "+" in m:
        return -15, "הציון הותאם מטה עקב קילומטראז׳ גבוה מאוד (200K+). מומלץ לשים דגש על גיר/מנוע/מערכות עזר."
    if "150" in m and "200" in m:
        return -10, "הציון הותאם מטה עקב קילומטראז׳ גבוה (150–200 אלף ק״מ)."
    if "100" in m and "150" in m:
        return -5, "הציון הותאם מעט מטה עקב קילומטראז׳ בינוני-גבוה (100–150 אלף ק״מ)."
    return 0, None

def mileage_is_close(requested: str, stored: str, thr: float = 0.92) -> bool:
    if requested is None or stored is None:
        return False
    return similarity(str(requested), str(stored)) >= thr

# =========================
# ===== Cache lookup ======
# =========================
def match_hits_core(recent: pd.DataFrame, year: int, make: str, model: str, sub_model: Optional[str], th: float):
    mk, md, sm = normalize_text(make), normalize_text(model), normalize_text(sub_model or "")
    use_sub = len(sm) > 0
    cand = recent[
        (recent["year"].astype("Int64") == int(year)) &
        (recent["make"].apply(lambda x: similarity(x, mk) >= th)) &
        (recent["model"].apply(lambda x: similarity(x, md) >= th))
    ]
    if use_sub and "sub_model" in recent.columns:
        cand = cand[cand["sub_model"].apply(lambda x: similarity(x, sm) >= th)]
    if "date" in cand.columns:
        cand = cand.sort_values("date")
    return cand

def get_cached_from_sheet(make: str, model: str, sub_model: str, year: int, mileage_range: str, max_days=45):
    """
    מחזיר: parsed_row, df, used_fallback, mileage_matched
    mileage_matched=False -> נציג Cache עם אזהרת ק״מ בלבד
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

    hits = pd.DataFrame()
    for th in (0.97, 0.93):
        hits = match_hits_core(recent, year, make, model, sub_model, th)
        if not hits.empty:
            break
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
        sources = safe_json_parse(r.get("sources"), []) or r.get("sources","")

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
            "sources": sources,
            "recommended_checks": recommended_checks,
            "common_competitors_brief": competitors,
            "last_date": last_date_str,
            "cached_mileage_range": r.get("mileage_range", "")
        }

    parsed_row = row_to_parsed(best.to_dict())
    parsed_row["is_aggregate"] = False
    parsed_row["count"] = int(len(hits))
    return parsed_row, df, used_fallback, mileage_matched

# =========================
# ===== Model calling =====
# =========================
def build_prompt(make, model, sub_model, year, fuel_type, transmission, mileage_range):
    extra = f" תת-דגם/תצורה: {sub_model}" if sub_model else ""
    return f"""
אתה מומחה לאמינות רכבים בישראל עם גישה לחיפוש אינטרנטי.
הניתוח חייב להתייחס ספציפית לטווח הקילומטראז' הנתון.
חובה לבצע חיפוש עדכני בעברית ובאנגלית ממקורות אמינים בלבד.
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
  "base_score_calculated": "מספר (0-100), מבוסס על המשקלות",
  "common_issues": ["תקלות נפוצות בעברית (רלוונטיות לק\"מ)"],
  "avg_repair_cost_ILS": "מספר ממוצע",
  "issues_with_costs": [
    {{"issue": "שם התקלה", "avg_cost_ILS": "מספר", "source": "מקור", "severity": "נמוך/בינוני/גבוה"}}
  ],
  "reliability_summary": "סיכום בעברית (להתייחס להשפעת הק\"מ)",
  "sources": ["רשימת אתרים"],
  "recommended_checks": ["בדיקות מומלצות ספציפיות לדגם זה במוסך"],
  "common_competitors_brief": [
      {{"model": "שם מתחרה 1", "brief_summary": "סיכום אמינות קצר של המתחרה"}},
      {{"model": "שם מתחרה 2", "brief_summary": "סיכום אמינות קצר של המתחרה"}}
  ]
}}

🧮 משקלות לחישוב base_score_calculated (מתוך 100):
מנוע/גיר (35%), חשמל/אלקטרוניקה (20%), מתלים/בלמים (10%), עלות תחזוקה (15%), שביעות רצון (15%), ריקולים (5%).
(הציון לכל קטגוריה הוא 1-10, תכפיל ב-10 כדי לקבל ציון מתוך 100 לכל קטגוריה לפני השקלול)

רכב: {make} {model}{extra} {int(year)}
טווח קילומטראז': {mileage_range}
סוג דלק: {fuel_type}
תיבת הילוכים: {transmission}
כתוב בעברית בלבד.
""".strip()

def call_model_with_retry(prompt: str):
    """Try PRIMARY_MODEL then FALLBACK with retries & backoff. Returns parsed JSON (dict) or raises."""
    models_chain = [PRIMARY_MODEL, FALLBACK_MODEL]
    last_err = None
    for model_name in models_chain:
        try:
            llm = genai.GenerativeModel(model_name)
        except Exception as e:
            last_err = e
            continue

        for attempt in range(1, RETRIES + 1):
            try:
                with st.spinner(f"פונה למודל {model_name} (ניסיון {attempt}/{RETRIES})..."):
                    resp = llm.generate_content(prompt)
                raw = (getattr(resp, "text", "") or "").strip()
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
    raise RuntimeError(f"All model attempts failed. Last error: {repr(last_err)}")

# =========================
# ======== Render =========
# =========================
def render_like_model(parsed_data: dict, source_tag: str, km_warn: bool = False, mileage_note: Optional[str] = None):
    base_score = int(parsed_data.get("base_score_calculated", 0) or 0)
    summary = parsed_data.get("reliability_summary", "") or ""
    score_breakdown = parsed_data.get("score_breakdown", {}) or {}
    issues_list = parsed_data.get("common_issues", []) or []
    detailed_costs_list = parsed_data.get("issues_with_costs", []) or []
    recommended_checks = parsed_data.get("recommended_checks", []) or []
    competitors = parsed_data.get("common_competitors_brief", []) or []
    avg_cost = parsed_data.get("avg_repair_cost_ILS", None)

    st.metric(label="ציון אמינות משוקלל", value=f"{base_score} / 100")

    if km_warn:
        st.warning("⚠️ שימו לב — טווח הק״מ שונה מהנתון שהוזן. ייתכן שהציון גבוה/נמוך יותר בהתאם לקילומטראז'.")
    if mileage_note:
        st.info(mileage_note)

    if summary:
        st.write(summary)

    tab1, tab2, tab3, tab4 = st.tabs(["פירוט הציון", "תקלות ועלויות", "בדיקות מומלצות", "מתחרים"])

    with tab1:
        st.markdown("#### 📊 פירוט הציון (1-10)")
        if score_breakdown:
            c1, c2, c3 = st.columns(3)
            c1.metric("מנוע וגיר", f"{score_breakdown.get('engine_transmission_score', 'N/A')}/10")
            c2.metric("חשמל ואלקטרוניקה", f"{score_breakdown.get('electrical_score', 'N/A')}/10")
            c3.metric("מתלים ובלמים", f"{score_breakdown.get('suspension_brakes_score', 'N/A')}/10")
            c1.metric("עלות אחזקה", f"{score_breakdown.get('maintenance_cost_score', 'N/A')}/10")
            c2.metric("שביעות רצון", f"{score_breakdown.get('satisfaction_score', 'N/A')}/10")
            c3.metric("ריקולים", f"{score_breakdown.get('recalls_score', 'N/A')}/10")
        else:
            st.info("אין נתוני פירוט ציון זמינים מהמאגר לרכב זה.")

    with tab2:
        if issues_list:
            st.markdown("**🔧 תקלות נפוצות:**")
            for i in issues_list:
                st.markdown(f"- {i}")
        if detailed_costs_list:
            st.markdown("**💰 עלויות תיקון (אינדיקטיבי):**")
            for item in detailed_costs_list:
                if isinstance(item, dict):
                    issue = item.get("issue","")
                    cost  = item.get("avg_cost_ILS", 0)
                    severity = item.get("severity", "")
                    tag = f" (חומרה: {severity})" if severity else ""
                    try:
                        cost_txt = f"{int(float(cost))}"
                    except Exception:
                        cost_txt = str(cost)
                    st.markdown(f"- {issue}: כ-{cost_txt} ₪{tag}")
        if not issues_list and not detailed_costs_list:
            st.info("אין מידע על תקלות/עלויות שמורות למקרה זה.")

    with tab3:
        if recommended_checks:
            st.markdown("**🔬 מה כדאי לבדוק במוסך?**")
            for check in recommended_checks:
                st.markdown(f"- {check}")
        else:
            st.info("אין המלצות בדיקה ספציפיות למודל זה במאגר.")

    with tab4:
        if competitors:
            st.markdown("**🚗 מתחרים נפוצים**")
            for comp in competitors:
                st.markdown(f"**{comp.get('model', '')}:** {comp.get('brief_summary', '')}")
        else:
            st.info("אין נתוני מתחרים שמורים למודל זה.")

    if avg_cost not in [None, "", "nan"]:
        try:
            st.info(f"עלות תחזוקה ממוצעת: כ-{int(float(avg_cost))} ₪")
        except Exception:
            st.info(f"עלות תחזוקה ממוצעת (אינדיקטיבי): {avg_cost}")

    if source_tag:
        st.caption(source_tag)

# =========================
# === Mileage Apply/Notes =
# =========================
def apply_mileage_logic(result_obj: dict, requested_mileage: str) -> Tuple[dict, Optional[str]]:
    delta, note = mileage_adjustment(requested_mileage)
    if delta != 0:
        try:
            base = int(result_obj.get("base_score_calculated") or 0)
        except Exception:
            base = 0
        new_base = max(0, min(100, base + delta))
        result_obj["base_score_calculated"] = new_base
    return result_obj, note

# =========================
# =========== UI ==========
# =========================

# מצב — ידני/ברירת מחדל
if "advanced_mode" not in st.session_state:
    st.session_state.advanced_mode = False

# מתג למעלה (לפי בקשתך שנבחר מיקום מיטבי)
mode_col1, mode_col2 = st.columns([1, 2])
with mode_col1:
    if st.button("⚙️ מצב מתקדם — הזנה חופשית", type="secondary"):
        st.session_state.advanced_mode = not st.session_state.advanced_mode
with mode_col2:
    st.caption("ברירת מחדל: בחירה מרשימות + תת־דגם חופשי • במצב מתקדם: הזנת יצרן/דגם/שנה ידנית")

st.markdown("### 🔍 בחירת יצרן, דגם ותת-דגם")

# קלטים משותפים
mileage_ranges = ["עד 50,000 ק\"מ", "50,000 - 100,000 ק\"מ", "100,000 - 150,000 ק\"מ", "150,000 - 200,000 ק\"מ", "200,000+ ק\"מ"]
col_top1, col_top2 = st.columns(2)
with col_top1:
    mileage_range = st.selectbox("טווח קילומטראז':", mileage_ranges, index=2)
with col_top2:
    fuel_type = st.selectbox("סוג דלק:", ["בנזין", "דיזל", "היברידי", "חשמלי", "אחר"], index=0)

transmission = st.selectbox("תיבת הילוכים:", ["אוטומטית", "ידנית"], index=0)

# === מצב ברירת מחדל (רשימות) ===
if not st.session_state.adv