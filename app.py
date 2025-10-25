
# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v3.0.1
# Sheets + Always-On Diagnostics + Smart Cache (45d Hard) + No Auth
# ===========================================================

import json, re, datetime, difflib, traceback
import pandas as pd
import streamlit as st
from json_repair import repair_json
import google.generativeai as genai

# ---------------- UI ----------------
st.set_page_config(page_title="🚗 Car Reliability Analyzer (Sheets)", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# ---------------- Secrets ----------------
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# ---------------- Model ----------------
if not GEMINI_API_KEY:
    st.error("⚠️ חסר GEMINI_API_KEY ב-Secrets.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel("gemini-2.5-flash")

# ---------------- Models dictionary ----------------
from car_models_dict import israeli_car_market_full_compilation

# ---------------- Helpers ----------------
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = re.sub(r"\(.*?\)", " ", str(s))
    s = re.sub(r"[^0-9A-Za-zא-ת]+", " ", s)
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

# ---------------- User ID (ללא הרשמה — always anonymous) ----------------
user_id = "anonymous"

# ---------------- Connectivity diagnostics to Google Sheets ----------------
def _ok(step):    return {"step": step, "status": "✅ OK", "hint": ""}
def _fail(step, why, fix): return {"step": step, "status": f"❌ FAIL - {why}", "hint": fix}

def run_connectivity_diagnostics():
    results = []

    if GEMINI_API_KEY: results.append(_ok("GEMINI_API_KEY"))
    if GOOGLE_SHEET_ID: results.append(_ok("GOOGLE_SHEET_ID"))
    if GOOGLE_SERVICE_ACCOUNT_JSON: results.append(_ok("GOOGLE_SERVICE_ACCOUNT_JSON"))
    else:
        results.append(_fail("GOOGLE_SERVICE_ACCOUNT_JSON", "missing", "הדבק JSON תקין ב-secrets."))
        return results, None, None, None

    try:
        svc = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        if "\\n" in svc.get("private_key",""):
            svc["private_key"] = svc["private_key"].replace("\\n","\n")
        results.append(_ok("Parsing JSON"))
    except Exception as e:
        results.append(_fail("Parsing JSON", "invalid", repr(e)))
        return results, None, None, None

    required = ["type","project_id","private_key_id","private_key","client_email","client_id","token_uri"]
    if not all(k in svc for k in required):
        results.append(_fail("Required JSON Keys", "missing", "ייצא מחדש מפתח JSON מ-GCP."))
        return results, None, None, None
    results.append(_ok("Required JSON Keys"))

    try:
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
        results.append(_ok("gspread Auth"))
    except Exception as e:
        results.append(_fail("gspread Auth", "fail", repr(e)))
        return results, None, None, None

    try:
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        results.append(_ok("Open Sheet ID"))
    except Exception as e:
        results.append(_fail(
            "Open Sheet ID", "PermissionError",
            "🚫 שתף את הגיליון עם ה-client_email + Editor.",
        ))
        return results, None, None, None

    try:
        ws = sh.sheet1
        results.append(_ok("Access sheet1"))
    except Exception as e:
        results.append(_fail("Access sheet1", "missing", repr(e)))
        return results, sh, None, None

    try:
        headers = [
            "date","user_id","make","model","year","fuel","transmission",
            "base_score","avg_cost","issues","search_performed"
        ]
        current = ws.row_values(1)
        if [c.lower() for c in current] != headers:
            ws.update("A1",[headers], value_input_option="USER_ENTERED")
        results.append(_ok("Headers OK"))
    except Exception as e:
        results.append(_fail("Headers", "write fail", repr(e)))
        return results, sh, ws, gc

    return results, sh, ws, gc

diag_results, sh, ws, gc = run_connectivity_diagnostics()
st.markdown("### 🧪 דיאגנוסטיקה")
for r in diag_results:
    st.markdown(f"- **{r['step']}** → {r['status']}")
if ws is None:
    st.stop()

# ---------------- Sheet I/O ----------------
def sheet_to_df() -> pd.DataFrame:
    try:
        recs = ws.get_all_records()
    except Exception as e:
        st.error("❌ כשל בקריאת נתונים מהשיטס")
        st.code(repr(e))
        return pd.DataFrame()
    return pd.DataFrame(recs) if recs else pd.DataFrame(columns=[
        "date","user_id","make","model","year","fuel","transmission",
        "base_score","avg_cost","issues","search_performed"
    ])

def append_row_to_sheet(row_dict: dict):
    order = ["date","user_id","make","model","year","fuel","transmission",
             "base_score","avg_cost","issues","search_performed"]
    row = [row_dict.get(k,"") for k in order]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error("❌ כשל בכתיבה לשיטס")
        st.code(repr(e))

# ---------------- Global Limit Only ----------------
GLOBAL_DAILY_LIMIT = 1000

def within_daily_global_limit(df: pd.DataFrame):
    today = datetime.date.today().isoformat()
    cnt = len(df[df.get("date","").astype(str) == today]) if not df.empty and "date" in df.columns else 0
    return (cnt < GLOBAL_DAILY_LIMIT, cnt)

# ---------------- Smart Cache (45d Hard) ----------------
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
        base_score = pd.to_numeric(hits["base_score"], errors="coerce").dropna()
        avg_cost  = pd.to_numeric(hits["avg_cost"], errors="coerce").dropna()
        return {
            "is_aggregate": True,
            "count": int(len(hits)),
            "base_score": int(round(base_score.mean())) if not base_score.empty else None,
            "avg_cost": int(round(avg_cost.mean())) if not avg_cost.empty else None,
            "issues": "; ".join([str(x) for x in hits["issues"].astype(str).tail(3)]),
            "search_performed": "true (history aggregate)",
            "last_date": str(hits.iloc[-1]["date"].date()) if not hits.empty else None
        }, df

    row = hits.iloc[-1].to_dict()
    row["is_aggregate"] = False
    row["count"] = int(len(hits))
    return row, df

# ---------------- UI Selection ----------------
st.markdown("### 🔍 בחירת יצרן, דגם ושנתון")
make_list = sorted(israeli_car_market_full_compilation.keys())
make_choice = st.selectbox("בחר יצרן:", ["בחר..."] + make_list, index=0)
make_input  = st.text_input("או הזן שם יצרן ידנית:")

selected_make = make_choice if make_choice != "בחר..." else make_input.strip()
selected_make = selected_make or ""

selected_model = ""
year_range = None

if selected_make in israeli_car_market_full_compilation:
    models = israeli_car_market_full_compilation[selected_make]
    model_choice = st.selectbox(f"דגם של {selected_make}:", ["בחר דגם..."] + models, index=0)
    model_input  = st.text_input("או הזן דגם ידנית:")
    selected_model = model_choice if model_choice != "בחר דגם..." else model_input.strip()

    if selected_model:
        yr_start, yr_end = parse_year_range_from_model_label(selected_model)
        if yr_start and yr_end:
            year_range = (yr_start, yr_end)
else:
    if selected_make:
        selected_model = st.text_input("שם דגם:")

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

# ---------------- Run Button ----------------
if st.button("בדוק אמינות"):
    if not selected_make or not selected_model:
        st.error("יש להזין שם יצרן ודגם תקינים.")
        st.stop()

    df_all = sheet_to_df()
    ok_global, total_global = within_daily_global_limit(df_all)
    if not ok_global:
        st.error(f"❌ חציתם את מגבלת {GLOBAL_DAILY_LIMIT} הבדיקות היומיות (בוצעו {total_global}). נסו מחר.")
        st.stop()

    # ✅ Cache first — ללא Gemini אם יש אפילו אחת אחרונה ≤45 יום
    st.info(f"בודק Cache בשיטס עבור {selected_make} {selected_model} ({int(year)})...")
    cached_row, _ = get_cached_from_sheet(selected_make, selected_model, int(year), max_days=45)

    if cached_row:
        if cached_row.get("is_aggregate"):
            st.success(f"✅ {cached_row['count']} תוצאות עדכניות (≤45 יום). מציג ממוצע יציב — ללא Gemini.")
            if cached_row.get("base_score") is not None:
                st.subheader(f"ציון אמינות כולל: {int(cached_row['base_score'])}/100")
            if cached_row.get("avg_cost") is not None:
                st.info(f"עלות תחזוקה ממוצעת: כ-{int(float(cached_row['avg_cost']))} ₪")
            st.write(f"תקלות נפוצות: {cached_row.get('issues','—')}")
            st.stop()
        else:
            st.success("✅ נמצאה תוצאה עדכנית ≤45 יום — ללא Gemini.")
            st.subheader(f"ציון אמינות כולל: {int(cached_row.get('base_score',0))}/100")
            if cached_row.get("avg_cost") not in [None, "", "nan"]:
                st.info(f"עלות תחזוקה ממוצעת: כ-{int(float(cached_row.get('avg_cost',0)))} ₪")
            st.write(f"תקלות נפוצות: {cached_row.get('issues','—')}")
            st.stop()

    # ---------------- No Cache → Gemini ----------------
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

    if parsed.get("search_performed", False):
        st.success("🌐 בוצע חיפוש אינטרנטי בזמן אמת.")
    else:
        st.warning("⚠️ לא בוצע חיפוש אינטרנטי — ייתכן שהמידע חלקי.")

    st.subheader(f"ציון אמינות כולל: {base_score}/100")
    st.write(summary)

    if issues:
        st.markdown("**🔧 תקלות נפוצות:**")
        for i in issues:
            st.markdown(f"- {i}")

    detailed_costs = parsed.get("issues_with_costs", [])
    if detailed_costs:
        st.markdown("**💰 עלויות תיקון:**")
        for item in detailed_costs:
            st.markdown(f"- {item.get('issue','')}: כ-{item.get('avg_cost_ILS', 0)} ₪ (מקור: {item.get('source','')})")

    # ✅ Save new search
    append_row_to_sheet({
        "date": datetime.date.today().isoformat(),
        "user_id": user_id,
        "make": normalize_text(selected_make),
        "model": normalize_text(selected_model),
        "year": int(year),
        "fuel": fuel_type,
        "transmission": transmission,
        "base_score": base_score,
        "avg_cost": avg_cost,
        "issues": "; ".join(issues) if isinstance(issues, list) else str(issues),
        "search_performed": "true"
    })
    st.info("💾 נשמר לשיטס בהצלחה.")