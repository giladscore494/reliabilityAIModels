# -*- coding: utf-8 -*-
# ===========================================================
# 🚗 Car Reliability Analyzer – Israel (v4.0.0 • Full)
# Sheets + 45d Cache • No blocking inputs • Advanced Mode toggle
# Free-text sub-model (soft counter only) • A→B sub-model fallback
# Mileage penalty by range • Global 1000/day limit • Clean errors
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

SOFT_MAX_LEN = 30                 # מונה תווים בלבד — אין חסימה
GLOBAL_DAILY_LIMIT = 1000         # מגבלה גלובלית (ללא זיהוי משתמש)

st.set_page_config(page_title="🚗 Car Reliability Analyzer (Sheets)", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# =========================
# ======== Secrets ========
# =========================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

if not GEMINI_API_KEY:
    st.error("❌ חסר GEMINI_API_KEY ב-Secrets.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)

# =========================
# === Models dictionary ===
# =========================
# אם אין קובץ car_models_dict.py נטען מילון ברירת-מחדל בסיסי
try:
    from car_models_dict import israeli_car_market_full_compilation
except Exception:
    israeli_car_market_full_compilation = {
        "Volkswagen": [
            "Golf (2004-2025)",
            "Polo (2005-2025)",
            "Passat (2005-2025)",
            "Scirocco (2008-2017)"
        ],
        "Toyota": [
            "Corolla (2008-2025)",
            "Yaris (2008-2025)",
            "CHR (2016-2025)"
        ],
        "Mazda": [
            "Mazda3 (2003-2025)",
            "Mazda6 (2003-2021)",
            "CX-5 (2012-2025)"
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
    m = re.search(r"\((\d{4})\s*-\s*(\d{4})\)", str(model_label))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)

def safe_json_parse(value: Any, default=None):
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
            fixed = repair_json(s)
            return json.loads(fixed)
        except Exception:
            return default

def char_counter(label: str, value: str, soft_max: int = SOFT_MAX_LEN):
    ln = len(value or "")
    suffix = f" (מומלץ עד {soft_max})" if ln > soft_max else ""
    st.caption(f"{label}: {ln} תווים{suffix}")

# =========================
# ===== Sheets Layer ======
# =========================
REQUIRED_HEADERS = [
    "date","user_id","make","model","sub_model","year","fuel","transmission",
    "mileage_range","base_score_calculated","score_breakdown","avg_cost",
    "issues","search_performed","reliability_summary","issues_with_costs",
    "sources","recommended_checks","common_competitors_brief"
]

def connect_sheet():
    if not (GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON):
        st.error("❌ אין חיבור למאגר (Secrets חסרים).")
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

        current = [c.lower() for c in ws.row_values(1)]
        if current != REQUIRED_HEADERS:
            ws.update("A1", [REQUIRED_HEADERS], value_input_option="USER_ENTERED")
        return ws
    except Exception as e:
        st.error("❌ אין חיבור למאגר (שיתוף/הרשאות/Sheet).")
        st.code(repr(e))
        st.stop()

ws = connect_sheet()

def sheet_to_df() -> pd.DataFrame:
    try:
        recs = ws.get_all_records()
        df = pd.DataFrame(recs) if recs else pd.DataFrame(columns=REQUIRED_HEADERS)
    except Exception as e:
        st.error("❌ כשל בקריאת המאגר.")
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
        st.error("❌ כשל בכתיבה למאגר.")
        st.code(repr(e))

# =========================
# ===== Limits/Quota ======
# =========================
def within_daily_global_limit(df: pd.DataFrame, limit=GLOBAL_DAILY_LIMIT) -> Tuple[bool, int]:
    today = datetime.date.today().isoformat()
    if df.empty or "date" not in df.columns:
        return True, 0
    try:
        cnt = len(df[df["date"].astype(str) == today])
    except Exception:
        cnt = 0
    return (cnt < limit), cnt

# =========================
# ==== Mileage logic  =====
# =========================
def mileage_adjustment(mileage_range: str) -> Tuple[int, Optional[str]]:
    """
    מחזיר (delta, note) כאשר delta מצורף לציון המשוקלל (שלילי לרוב),
    ו-note הוא טקסט הסבר להצגה למשתמש.
    """
    m = normalize_text(mileage_range or "")
    if not m:
        return 0, None
    if "200" in m and "+" in m:
        return -15, "הציון הותאם מטה עקב קילומטראז׳ גבוה מאוד (200K+)."
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
  "common_issues": ["תקלות נפוצות רלוונטיות לק\"מ"],
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
    last_err = None
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
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
    raise RuntimeError(f"Model failed: {repr(last_err)}")

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
        st.warning("⚠️ טווח הק״מ השמור שונה מהקלט. ייתכן שהציון היה משתנה לפי ק״מ.")
    if mileage_note:
        st.info(mileage_note)

    if summary:
        st.write(summary)

    tab1, tab2, tab3, tab4 = st.tabs(["פירוט הציון", "תקלות ועלויות", "בדיקות מומלצות", "מתחרים"])

    with tab1:
        st.markdown("#### 📊 פירוט (1–10)")
        keys = [
            ("engine_transmission_score", "מנוע וגיר"),
            ("electrical_score", "חשמל/אלקטרוניקה"),
            ("suspension_brakes_score", "מתלים/בלמים"),
            ("maintenance_cost_score", "עלות אחזקה"),
            ("satisfaction_score", "שביעות רצון"),
            ("recalls_score", "ריקולים"),
        ]
        for k, label in keys:
            v = score_breakdown.get(k, "N/A")
            st.write(f"- {label}: {v}/10")

    with tab2:
        if issues_list:
            st.markdown("**🔧 תקלות נפוצות:**")
            for i in issues_list:
                if i:
                    st.markdown(f"- {i}")
        if detailed_costs_list:
            st.markdown("**💰 עלויות תיקון (אינדיקטיבי):**")
            for item in detailed_costs_list:
                if isinstance(item, dict):
                    issue = item.get("issue","")
                    cost  = item.get("avg_cost_ILS", "")
                    severity = item.get("severity", "")
                    tag = f" (חומרה: {severity})" if severity else ""
                    try:
                        cost_txt = f"{int(float(cost))}"
                    except Exception:
                        cost_txt = str(cost)
                    st.markdown(f"- {issue}: כ-{cost_txt} ₪{tag}")
        if not issues_list and not detailed_costs_list:
            st.info("אין מידע תקלות/עלויות שמור למקרה זה.")

    with tab3:
        if recommended_checks:
            st.markdown("**🔬 בדיקות מומלצות במוסך:**")
            for check in recommended_checks:
                st.markdown(f"- {check}")
        else:
            st.info("אין המלצות בדיקה ספציפיות שמורות.")

    with tab4:
        if competitors:
            st.markdown("**🚗 מתחרים נפוצים**")
            for comp in competitors:
                st.markdown(f"**{comp.get('model', '')}:** {comp.get('brief_summary', '')}")
        else:
            st.info("אין נתוני מתחרים שמורים.")

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

# כפתור מצב מתקדם — במיקום עליון
mode_col1, mode_col2 = st.columns([1, 2])
with mode_col1:
    if st.button("⚙️ מצב מתקדם — הזנה חופשית", type="secondary"):
        st.session_state.advanced_mode = not st.session_state.advanced_mode
with mode_col2:
    st.caption("ברירת מחדל: רשימות יצרן/דגם + תת־דגם חופשי • מתקדם: הזנה ידנית מלאה")

st.markdown("### 🔍 בחירת יצרן, דגם ותת-דגם")

# קלטים משותפים ל-2 המצבים
mileage_ranges = [
    "עד 50,000 ק\"מ",
    "50,000 - 100,000 ק\"מ",
    "100,000 - 150,000 ק\"מ",
    "150,000 - 200,000 ק\"מ",
    "200,000+ ק\"מ"
]
col_top1, col_top2 = st.columns(2)
with col_top1:
    mileage_range = st.selectbox("טווח קילומטראז':", mileage_ranges, index=2)
with col_top2:
    fuel_type = st.selectbox("סוג דלק:", ["בנזין", "דיזל", "היברידי", "חשמלי", "אחר"], index=0)

transmission = st.selectbox("תיבת הילוכים:", ["אוטומטית", "ידנית"], index=0)

# ==== מצב ברירת מחדל (רשימות) ====
if not st.session_state.advanced_mode:
    make_list = sorted(israeli_car_market_full_compilation.keys())
    make_choice = st.selectbox("בחר יצרן:", ["בחר..."] + make_list, index=0)
    selected_make = make_choice if make_choice != "בחר..." else ""

    selected_model = ""
    year_range = None
    if selected_make:
        models = israeli_car_market_full_compilation.get(selected_make, [])
        model_choice = st.selectbox("בחר דגם:", ["בחר דגם..."] + models, index=0)
        selected_model = model_choice if model_choice != "בחר דגם..." else ""
        if selected_model:
            yr_start, yr_end = parse_year_range_from_model_label(selected_model)
            if yr_start and yr_end:
                year_range = (yr_start, yr_end)

    if year_range:
        year = st.number_input(f"שנת ייצור ({year_range[0]}–{year_range[1]}):", min_value=year_range[0], max_value=year_range[1], step=1)
    else:
        year = st.number_input("שנת ייצור:", min_value=1960, max_value=2025, step=1)

    # תת-דגם חופשי — אך ללא חסימה; רק מונה תווים
    sub_model = st.text_input("תת-דגם / תצורה (חופשי)")
    char_counter("תת-דגם", sub_model, SOFT_MAX_LEN)

# ==== מצב מתקדם (ידני מלא) ====
else:
    # נשמור את הבחירות הקודמות כערכי התחלה
    init_make = st.session_state.get("last_selected_make", "")
    init_model = st.session_state.get("last_selected_model", "")

    col_adv1, col_adv2 = st.columns(2)
    with col_adv1:
        selected_make = st.text_input("יצרן (ידני)", value=init_make)
        char_counter("יצרן", selected_make, SOFT_MAX_LEN)
    with col_adv2:
        selected_model = st.text_input("דגם (ידני)", value=init_model)
        char_counter("דגם", selected_model, SOFT_MAX_LEN)

    year = st.number_input("שנת ייצור (ידני)", min_value=1960, max_value=2025, step=1)
    sub_model = st.text_input("תת-דגם / תצורה (חופשי)")
    char_counter("תת-דגם", sub_model, SOFT_MAX_LEN)

# נשמור את בחירות ברירת המחדל לעזרה במעבר לעתיד
if not st.session_state.advanced_mode:
    st.session_state.last_selected_make = selected_make or ""
    st.session_state.last_selected_model = selected_model or ""

st.markdown("---")

# =========================
# ===== Submit Action =====
# =========================
submit = st.button("🔎 בדיקת אמינות")

if submit:
    # בדיקות רכות: אין חסימת אורך; רק וידוא שהוכנסו יצרן ודגם
    if not selected_make or not selected_model:
        st.warning("יש לבחור/להזין יצרן ודגם.")
        st.stop()

    # מגבלה יומית גלובלית
    all_df = sheet_to_df()
    ok_limit, cnt_today = within_daily_global_limit(all_df, GLOBAL_DAILY_LIMIT)
    if not ok_limit:
        st.error("הגעתם למגבלת הבדיקות היומית של המערכת. נסו שוב מחר.")
        st.stop()

    # נסה קריאה מה-Cache
    cached = None
    used_fallback = False
    mileage_matched = False
    try:
        cached, all_df, used_fallback, mileage_matched = get_cached_from_sheet(
            selected_make, selected_model, sub_model, int(year), mileage_range, max_days=45
        )
    except Exception as e:
        # לא עוצרים — ממשיכים למודל
        cached, used_fallback, mileage_matched = None, False, False

    if cached:
        # החלת התאמת ק"מ גם על Cache (אינדיקטיבי)
        cached, mileage_note = apply_mileage_logic(cached, mileage_range)
        tag = f"📚 נשלף מהמאגר • עדכון אחרון: {cached.get('last_date','') or 'לא ידוע'} • {'התעלמנו מתת-דגם' if used_fallback else 'התאמה מלאה'}"
        render_like_model(cached, tag, km_warn=(not mileage_matched), mileage_note=mileage_note)
    else:
        # קריאה למודל
        try:
            prompt = build_prompt(selected_make, selected_model, sub_model, int(year), fuel_type, transmission, mileage_range)
            result = call_model_with_retry(prompt)
        except Exception as e:
            st.error("❌ המודל נכשל בהחזרת נתונים.")
            st.code(repr(e))
            st.stop()

        # התאמת קילומטראז׳ לציון
        result, mileage_note = apply_mileage_logic(result, mileage_range)

        # כתיבה למאגר
        try:
            row = {
                "date": datetime.date.today().isoformat(),
                "user_id": "anonymous",
                "make": selected_make,
                "model": selected_model,
                "sub_model": sub_model or "",
                "year": int(year),
                "fuel": fuel_type,
                "transmission": transmission,
                "mileage_range": mileage_range,
                "base_score_calculated": result.get("base_score_calculated",""),
                "score_breakdown": json.dumps(result.get("score_breakdown", {}), ensure_ascii=False),
                "avg_cost": result.get("avg_repair_cost_ILS",""),
                "issues": "; ".join(result.get("common_issues", []) or []),
                "search_performed": bool(result.get("search_performed", True)),
                "reliability_summary": result.get("reliability_summary",""),
                "issues_with_costs": json.dumps(result.get("issues_with_costs", []), ensure_ascii=False),
                "sources": json.dumps(result.get("sources", []), ensure_ascii=False),
                "recommended_checks": json.dumps(result.get("recommended_checks", []), ensure_ascii=False),
                "common_competitors_brief": json.dumps(result.get("common_competitors_brief", []), ensure_ascii=False),
            }
            append_row_to_sheet(row)
        except Exception as e:
            # לא חוסם — רק מציג אזהרה וממשיך להציג תוצאה
            st.warning("אזהרה: לא הצלחנו לשמור את התוצאה למאגר.")
            st.code(repr(e))

        render_like_model(result, "🤖 נשלף כעת מהמודל (ונשמר במאגר אם התאפשר)", km_warn=False, mileage_note=mileage_note)

# =========================
# ===== UX Explanations ===
# =========================
with st.expander("ℹ️ הסבר על מצבי הקלט", expanded=False):
    st.write(
        "- **ברירת מחדל**: בחירה מרשימות יצרן/דגם, ותת־דגם חופשי ללא חסימת תווים (רק מונה תווים).\n"
        "- **מצב מתקדם — הזנה חופשית**: הזנת יצרן/דגם/שנה ידנית. שימושי לדגמים נדירים או שנים לא ברשימה.\n"
        "- אין חסימה על אורך — הבקשה תמיד תישלח; רק תוצג אינדיקציה רכה."
    )