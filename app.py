# -*- coding: utf-8 -*-
# Car Reliability Analyzer – Israel (v3.1.3)
# Sheets + Smart 45d Cache + No Auth + Manual Input Limits (3 words & 30 chars)
# Cached results render EXACTLY like live model responses (Gemini)

import json, re, datetime, difflib, traceback
import pandas as pd
import streamlit as st
from json_repair import repair_json
import google.generativeai as genai

# ---------- UI ----------
st.set_page_config(page_title="🚗 Car Reliability Analyzer (Sheets)", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# ---------- Secrets ----------
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# ---------- Model ----------
if not GEMINI_API_KEY:
    st.error("⚠️ חסר GEMINI_API_KEY ב-Secrets.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel("gemini-2.5-flash")

# ---------- Models dictionary ----------
from car_models_dict import israeli_car_market_full_compilation

# ---------- Helpers ----------
ALLOWED_PATTERN = r"^[A-Za-zא-ת0-9\- ]+$"
MAX_WORDS = 3
MAX_LEN = 30
ERR_MSG = "הזנה ארוכה מדי — ניתן להזין עד 3 מילים או 30 תווים"

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = re.sub(r"\(.*?\)", " ", str(s))
    s = re.sub(r"[^0-9A-Za-zא-ת\- ]+", " ", s)  # מותר: אותיות/ספרות/רווח/מקף
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def parse_year_range_from_model_label(model_label: str):
    m = re.search(r"\((\d{4})\s*-\s*(\d{4})", str(model_label))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)

def build_prompt(make, model, year, fuel_type, transmission):
    return f"""
אתה מומחה לאמינות רכבים בישראל עם גישה לחיפוש אינטרנטי.
חובה לבצע חיפוש עדכני בעברית ובאנגלית ממקורות אמינים בלבד.
החזר JSON בלבד עם המפתח/ערך הבאים:

{{
  "search_performed": true או false,
  "base_score": מספר בין 0 ל-100,
  "common_issues": [תקלות נפוצות בעברית],
  "avg_repair_cost_ILS": מספר ממוצע,
  "issues_with_costs": [
    {{"issue": "שם התקלה בעברית", "avg_cost_ILS": מספר, "source": "מקור"}}
  ],
  "reliability_summary": "סיכום בעברית על רמת האמינות",
  "sources": ["רשימת אתרים"]
}}

🧮 משקלות לציון אמינות:
- מנוע/גיר – 35%
- חשמל ואלקטרוניקה – 20%
- מתלים ובלמים – 10%
- עלות תחזוקה – 15%
- שביעות רצון – 15%
- ריקולים – 5%

רכב: {make} {model} {int(year)}
סוג דלק: {fuel_type}
תיבת הילוכים: {transmission}
כתוב בעברית בלבד.
""".strip()

def safe_json_parse(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        try:
            fixed = repair_json(s)
            return json.loads(fixed)
        except Exception:
            return None

def validate_input_or_stop(value: str):
    if not value:
        return ""
    if not re.match(ALLOWED_PATTERN, value):
        st.error(ERR_MSG); st.stop()
    words = value.strip().split()
    if len(words) > MAX_WORDS:
        st.error(ERR_MSG); st.stop()
    if len(value.strip()) > MAX_LEN:
        st.error(ERR_MSG); st.stop()
    return value.strip()

# ---------- Sheets connectivity (no debug UI) ----------
def connect_sheet():
    if not (GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON):
        st.error("❌ אין חיבור למאגר — חסרים Secrets.")
        st.stop()
    try:
        svc = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        if "\\n" in svc.get("private_key",""):
            svc["private_key"] = svc["private_key"].replace("\\n","\n")
        from google.oauth2.service_account import Credentials
        import gspread
        credentials = Credentials.from_service_account_info(
            svc,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ],
        )
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        ws = sh.sheet1
        headers = [
            "date","user_id","make","model","year","fuel","transmission",
            "base_score","avg_cost","issues","search_performed",
            "reliability_summary","issues_with_costs","sources"
        ]
        current = ws.row_values(1)
        if [c.lower() for c in current] != headers:
            ws.update("A1",[headers], value_input_option="USER_ENTERED")
        return ws
    except Exception:
        st.error("❌ אין חיבור למאגר — בדוק הרשאות/שיתוף לשירות.")
        st.stop()

ws = connect_sheet()

# ---------- Sheet I/O ----------
def sheet_to_df() -> pd.DataFrame:
    try:
        recs = ws.get_all_records()
    except Exception as e:
        st.error("❌ כשל בקריאת נתונים מהמאגר (Google Sheets)")
        st.code(repr(e))
        return pd.DataFrame(columns=[
            "date","user_id","make","model","year","fuel","transmission",
            "base_score","avg_cost","issues","search_performed",
            "reliability_summary","issues_with_costs","sources"
        ])
    return pd.DataFrame(recs) if recs else pd.DataFrame(columns=[
        "date","user_id","make","model","year","fuel","transmission",
        "base_score","avg_cost","issues","search_performed",
        "reliability_summary","issues_with_costs","sources"
    ])

def append_row_to_sheet(row_dict: dict):
    order = ["date","user_id","make","model","year","fuel","transmission",
             "base_score","avg_cost","issues","search_performed",
             "reliability_summary","issues_with_costs","sources"]
    row = [row_dict.get(k,"") for k in order]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error("❌ כשל בכתיבה למאגר")
        st.code(repr(e))

# ---------- Limits ----------
GLOBAL_DAILY_LIMIT = 1000

def within_daily_global_limit(df: pd.DataFrame, limit=GLOBAL_DAILY_LIMIT):
    today = datetime.date.today().isoformat()
    cnt = len(df[df.get("date","").astype(str) == today]) if not df.empty and "date" in df.columns else 0
    return (cnt < limit, cnt)

# ---------- Smart Cache (45d, Hardened) ----------
def get_cached_from_sheet(make: str, model: str, year: int, max_days=45):
    df = sheet_to_df()
    if df.empty:
        return None, df

    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    except Exception:
        pass

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=max_days)
    recent = df[df["date"] >= cutoff] if "date" in df.columns else df

    mk = normalize_text(make)
    md = normalize_text(model)

    hits = pd.DataFrame()
    for th in (0.97, 0.93):
        cand = recent[
            (recent["year"].astype("Int64") == int(year)) &
            (recent["make"].apply(lambda x: similarity(x, mk) >= th)) &
            (recent["model"].apply(lambda x: similarity(x, md) >= th))
        ]
        if not cand.empty:
            hits = cand.sort_values("date")
            break

    if hits.empty:
        return None, df

    if len(hits) >= 3:
        base_score_series = pd.to_numeric(hits["base_score"], errors="coerce").dropna()
        avg_cost_series  = pd.to_numeric(hits["avg_cost"], errors="coerce").dropna()
        issues_tail = "; ".join([str(x) for x in hits["issues"].astype(str).tail(3)])
        last_row = hits.iloc[-1].to_dict()
        issues_with_costs = safe_json_parse(last_row.get("issues_with_costs"))
        reliability_summary = last_row.get("reliability_summary") or ""
        return {
            "is_aggregate": True,
            "count": int(len(hits)),
            "base_score": int(round(base_score_series.mean())) if not base_score_series.empty else None,
            "avg_cost": int(round(avg_cost_series.mean())) if not avg_cost_series.empty else None,
            "issues": issues_tail,
            "issues_with_costs": issues_with_costs if isinstance(issues_with_costs, list) else [],
            "reliability_summary": reliability_summary,
            "search_performed": "true (history aggregate)",
            "last_date": str(hits.iloc[-1]["date"].date()) if not hits.empty else None,
            "sources": last_row.get("sources","")
        }, df

    row = hits.iloc[-1].to_dict()
    row["is_aggregate"] = False
    row["count"] = int(len(hits))
    row["issues_with_costs"] = safe_json_parse(row.get("issues_with_costs")) or []
    row["reliability_summary"] = row.get("reliability_summary") or ""
    row["last_date"] = str(hits.iloc[-1]["date"].date())
    return row, df

# ---------- UI Selection (STRICT: 3 words & 30 chars; live + submit) ----------
st.markdown("### 🔍 בחירת יצרן, דגם ושנתון")

make_list = sorted(israeli_car_market_full_compilation.keys())
make_choice = st.selectbox("בחר יצרן מהרשימה:", ["בחר..."] + make_list, index=0)

make_input = st.text_input(
    "או הזן שם יצרן ידנית (עד 3 מילים / 30 תווים, מותר מקף):",
    max_chars=MAX_LEN
)
make_input = validate_input_or_stop(make_input) if make_input else ""
selected_make = make_choice if make_choice != "בחר..." else make_input
selected_make = selected_make or ""

selected_model = ""
year_range = None

if selected_make in israeli_car_market_full_compilation:
    models = israeli_car_market_full_compilation[selected_make]
    model_choice = st.selectbox(f"בחר דגם של {selected_make}:", ["בחר דגם..."] + models, index=0)

    model_input = st.text_input(
        "או הזן דגם ידנית (עד 3 מילים / 30 תווים, מותר מקף):",
        max_chars=MAX_LEN
    )
    model_input = validate_input_or_stop(model_input) if model_input else ""
    selected_model = model_choice if model_choice != "בחר דגם..." else model_input
    selected_model = selected_model or ""

    if selected_model:
        yr_start, yr_end = parse_year_range_from_model_label(selected_model)
        if yr_start and yr_end:
            year_range = (yr_start, yr_end)
else:
    if selected_make:
        model_input = st.text_input(
            "שם דגם (הקלדה ידנית — עד 3 מילים / 30 תווים, מותר מקף):",
            max_chars=MAX_LEN
        )
        model_input = validate_input_or_stop(model_input) if model_input else ""
        selected_model = model_input.strip()

if year_range:
    year = st.number_input(f"שנת ייצור ({year_range[0]}–{year_range[1]}):",
                           min_value=year_range[0], max_value=year_range[1], step=1)
else:
    year = st.number_input("שנת ייצור:", min_value=1960, max_value=2025, step=1)

col1, col2 = st.columns(2)
with col1:
    fuel_type = st.selectbox("סוג דלק:", ["בנזין", "דיזל", "היברידי", "חשמלי", "אחר"])
with col2:
    transmission = st.selectbox("תיבת הילוכים:", ["אוטומטית", "ידנית"])

st.markdown("---")

# ---------- Render helpers ----------
def render_like_model(base_score, summary, issues_list, detailed_costs_list, source_tag):
    st.subheader(f"ציון אמינות כולל: {int(base_score)}/100")
    if summary:
        st.write(summary)
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
                src   = item.get("source","")
                st.markdown(f"- {issue}: כ-{int(cost)} ₪ (מקור: {src})")
    if source_tag:
        st.caption(source_tag)

def explode_issues(issues_field):
    if issues_field is None:
        return []
    if isinstance(issues_field, list):
        return [str(x).strip() for x in issues_field if str(x).strip()]
    s = str(issues_field)
    if ";" in s:
        return [x.strip() for x in s.split(";") if x.strip()]
    if "," in s:
        return [x.strip() for x in s.split(",") if x.strip()]
    return [s] if s.strip() else []

# ---------- Run ----------
if st.button("בדוק אמינות"):
    if not selected_make or not selected_model:
        st.error("יש להזין שם יצרן ודגם תקינים.")
        st.stop()

    # ולידציה סופית גם אחרי הלחיצה
    for value in [selected_make, selected_model]:
        if value:
            if not re.match(ALLOWED_PATTERN, value): st.error(ERR_MSG); st.stop()
            if len(value.strip().split()) > MAX_WORDS: st.error(ERR_MSG); st.stop()
            if len(value.strip()) > MAX_LEN: st.error(ERR_MSG); st.stop()

    df_all = sheet_to_df()
    ok_global, total_global = within_daily_global_limit(df_all, limit=GLOBAL_DAILY_LIMIT)
    if not ok_global:
        st.error(f"❌ חציתם את מגבלת {GLOBAL_DAILY_LIMIT} הבדיקות היומיות (בוצעו {total_global}). נסו מחר.")
        st.stop()

    # ===== Cache first =====
    cached_row, _ = get_cached_from_sheet(selected_make, selected_model, int(year), max_days=45)
    if cached_row:
        base_score = cached_row.get("base_score", None)
        avg_cost   = cached_row.get("avg_cost", None)
        issues_raw = cached_row.get("issues", [])
        issues_list = explode_issues(issues_raw)
        detailed_costs = cached_row.get("issues_with_costs", []) or []
        summary = cached_row.get("reliability_summary", "") or ""
        last_date = cached_row.get("last_date", "")
        source_tag = f"✅ מקור: נתון קיים מהמאגר (נבדק: {last_date}). לא בוצעה פנייה למודל."

        if base_score is None and not issues_list and not detailed_costs and not summary:
            st.warning("🚧 אין סיכום/תקלות מהמאגר עבור הרכב הזה. מומלץ לבצע בדיקה עדכנית.")
            st.stop()

        if base_score is not None:
            render_like_model(base_score, summary, issues_list, detailed_costs, source_tag)
            if avg_cost not in [None, "", "nan"]:
                st.info(f"עלות תחזוקה ממוצעת: כ-{int(float(avg_cost))} ₪")
            st.stop()
        else:
            st.warning("🚧 אין ציון שמור במאגר עבור הרכב הזה. מומלץ לבצע בדיקה עדכנית.")
            st.stop()

    # ===== No cache → call Gemini =====
    prompt = build_prompt(selected_make, selected_model, int(year), fuel_type, transmission)
    try:
        with st.spinner("🌐 מבצע חיפוש אינטרנטי ומחשב ציון..."):
            resp = llm.generate_content(prompt)
            raw = (getattr(resp, "text", "") or "").strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            parsed = json.loads(m.group()) if m else json.loads(repair_json(raw))
    except Exception as e:
        st.error("שגיאה בעיבוד תשובת המודל:")
        st.code(repr(e))
        st.code(traceback.format_exc())
        st.stop()

    base_score = int(parsed.get("base_score", 0) or 0)
    issues = parsed.get("common_issues", [])
    avg_cost = parsed.get("avg_repair_cost_ILS", 0)
    summary = parsed.get("reliability_summary", "אין מידע.")
    detailed_costs = parsed.get("issues_with_costs", [])
    sources = parsed.get("sources", [])

    render_like_model(
        base_score,
        summary,
        issues,
        detailed_costs,
        "🌐 מקור: חיפוש בזמן אמת (Gemini)"
    )
    if avg_cost not in [None, "", "nan"]:
        st.info(f"עלות תחזוקה ממוצעת: כ-{int(float(avg_cost))} ₪")

    try:
        issues_str = "; ".join(issues) if isinstance(issues, list) else str(issues)
        issues_with_costs_str = json.dumps(detailed_costs, ensure_ascii=False)
        sources_str = json.dumps(sources, ensure_ascii=False) if isinstance(sources, list) else str(sources)
    except Exception:
        issues_str = str(issues)
        issues_with_costs_str = str(detailed_costs)
        sources_str = str(sources)

    append_row_to_sheet({
        "date": datetime.date.today().isoformat(),
        "user_id": "anonymous",
        "make": normalize_text(selected_make),
        "model": normalize_text(selected_model),
        "year": int(year),
        "fuel": fuel_type,
        "transmission": transmission,
        "base_score": base_score,
        "avg_cost": avg_cost,
        "issues": issues_str,
        "search_performed": "true",
        "reliability_summary": summary,
        "issues_with_costs": issues_with_costs_str,
        "sources": sources_str
    })

st.markdown("---")
st.caption("כל המידע מוצג כשירות עזר בלבד — אין לראות בתוצאה המלצה מקצועית.")