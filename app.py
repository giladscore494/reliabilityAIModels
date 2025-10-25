# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v2.0.0 (Sheets Edition)
# בדיקת אמינות רכב לפי יצרן, דגם ושנתון
# Google Sheets Cache · Smart Filter · Daily Limits · Fuel/Transmission · (Optional) Google Sign-In
# ===========================================================

import os, json, re, datetime, time
import pandas as pd
import streamlit as st
import difflib
from json_repair import repair_json
import google.generativeai as genai

# ==== Streamlit Base ====
st.set_page_config(page_title="🚗 Car Reliability Analyzer", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# ==== Secrets & Config ====
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID")  # ה-ID של הגיליון ששלחת
GOOGLE_CREDENTIALS = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")
USE_GOOGLE_OAUTH = st.secrets.get("USE_GOOGLE_OAUTH", "false").lower() == "true"
GOOGLE_OAUTH_CLIENT_ID = st.secrets.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = st.secrets.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

if not GEMINI_API_KEY or not GOOGLE_SHEET_ID or not GOOGLE_CREDENTIALS:
    st.error("⚠️ חסרים Secrets: GEMINI_API_KEY, GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ==== Car dictionary ====
from car_models_dict import israeli_car_market_full_compilation

# ==== Google Sheets via gspread ====
try:
    import gspread
    from google.oauth2.service_account import Credentials

    st.write("🔄 מנסה להתחבר ל-Google Sheets...")

    credentials = Credentials.from_service_account_info(
        GOOGLE_SERVICE_ACCOUNT_JSON,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    worksheet = sh.sheet1

    st.success("✅ חיבור ל-Google Sheets הצליח!")

except Exception as e:
    st.error(f"❌ כשל חיבור ל-Google Sheets:")
    st.code(str(e))
    st.stop()

# ==== Auth (Optional Google Sign-In → Fallback email) ====
def get_current_user_id():
    # אם תרצה Google Sign-In צד לקוח, אפשר לשלב רכיב JS/Component ייעודי.
    # כאן – Fallback פשוט: אם USE_GOOGLE_OAUTH=false → נשתמש בכתובת מייל ידנית.
    st.markdown("#### התחברות")
    if USE_GOOGLE_OAUTH and GOOGLE_OAUTH_CLIENT_ID:
        st.info("🔒 Google Sign-In מופעל בקונפיג, אך הרכיב אינו כלול כאן. נופל למצב הזנת מייל ידני.")
    email = st.text_input("הכנס אימייל לזיהוי (ללא סיסמה):", value=st.session_state.get("user_email",""))
    if email:
        st.session_state["user_email"] = email.strip().lower()
    return st.session_state.get("user_email","anonymous")

current_user = get_current_user_id()

# ==== Helpers ====
def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", str(s))).strip().lower()

def similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def parse_year_range_from_model_label(model_label: str):
    # דוגמה: "Corolla (1966-2025)" או "Colt (1962-2012, 2023-2025)" → נטפל בטווח הראשון
    m = re.search(r"\((\d{4})(?:\s*-\s*(\d{4}|)\s*)", model_label)
    if not m:
        # ניסיון נוסף: כל טווח 4 ספרות-4 ספרות
        m2 = re.search(r"(\d{4})\s*-\s*(\d{4})", model_label)
        if m2:
            start, end = m2.group(1), m2.group(2)
            return int(start), int(end)
        return None, None
    start, end = m.group(1), m.group(2) or "2025"
    try:
        return int(start), int(end)
    except:
        return None, None

def sheet_to_df():
    recs = ws.get_all_records()
    if not recs:
        return pd.DataFrame(columns=[
            "date","user_id","make","model","year","fuel","transmission",
            "base_score","avg_cost","issues","search_performed"
        ])
    df = pd.DataFrame(recs)
    # טיפוסים
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["make","model","fuel","transmission","issues","user_id"]:
        if c in df.columns:
            df[c] = df[c].astype(str).fillna("")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(int)
    if "base_score" in df.columns:
        df["base_score"] = pd.to_numeric(df["base_score"], errors="coerce")
    if "avg_cost" in df.columns:
        df["avg_cost"] = pd.to_numeric(df["avg_cost"], errors="coerce")
    if "search_performed" in df.columns:
        df["search_performed"] = df["search_performed"].astype(str)
    return df

def append_row_to_sheet(row_dict: dict):
    order = ["date","user_id","make","model","year","fuel","transmission",
             "base_score","avg_cost","issues","search_performed"]
    row = [row_dict.get(k,"") for k in order]
    ws.append_row(row, value_input_option="USER_ENTERED")

def within_daily_global_limit(df: pd.DataFrame, limit=1000) -> (bool, int):
    today = pd.Timestamp.now().date()
    df_today = df[df["date"].dt.date == today] if "date" in df.columns else pd.DataFrame()
    return (len(df_today) < limit, len(df_today))

def within_daily_user_limit(df: pd.DataFrame, user_id: str, limit=5) -> (bool, int):
    today = pd.Timestamp.now().date()
    user_today = df[(df["user_id"].str.lower()==str(user_id).lower()) & (df["date"].dt.date == today)] if "date" in df.columns else pd.DataFrame()
    return (len(user_today) < limit, len(user_today))

def get_cached_from_sheet(make: str, model: str, year: int, max_days=45):
    df = sheet_to_df()
    if df.empty:
        return None, df

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=max_days)
    recent = df[df["date"] >= cutoff]

    # ניקוי ו־fuzzy
    make_clean = normalize_text(make)
    model_clean = normalize_text(model)

    # התאמת יצרן/דגם (threshold גבוה כדי למנוע false)
    # תחילה התאמה חזקה (>=0.95), אם אין – נרד ל־0.90
    for th in [0.95, 0.90]:
        candidates = recent[
            (recent["year"] == int(year)) &
            (recent["make"].apply(lambda x: similar(x, make_clean) >= th)) &
            (recent["model"].apply(lambda x: similar(x, model_clean) >= th))
        ]
        if not candidates.empty:
            # ניקח את העדכנית ביותר
            candidates = candidates.sort_values("date")
            return candidates.iloc[-1].to_dict(), df

    return None, df

# ==== UI: Make → Model → Year + Fuel/Transmission ====
st.markdown("### 🔍 בחירת יצרן, דגם ושנתון")
make_list = sorted(israeli_car_market_full_compilation.keys())
make_choice = st.selectbox("בחר יצרן מהרשימה:", ["בחר..."] + make_list, index=0)
make_input = st.text_input("או הזן שם יצרן ידנית:")

if make_choice != "בחר...":
    selected_make = make_choice
elif make_input.strip():
    selected_make = make_input.strip()
else:
    selected_make = ""

selected_model = ""
year_range = None

if selected_make in israeli_car_market_full_compilation:
    models = israeli_car_market_full_compilation[selected_make]
    model_choice = st.selectbox(f"בחר דגם של {selected_make}:", ["בחר דגם..."] + models, index=0)
    model_input = st.text_input("או הזן דגם ידנית:")
    if model_choice != "בחר דגם...":
        selected_model = model_choice
    elif model_input.strip():
        selected_model = model_input.strip()

    # טווח שנים מהמילון (אם יש)
    if selected_model:
        start, end = parse_year_range_from_model_label(selected_model)
        if start and end:
            year_range = (start, end)
else:
    if selected_make:
        st.warning("️📋 יצרן לא במילון – הזן דגם ידנית:")
    selected_model = st.text_input("שם דגם:")

# שנתון: אם יש טווח – נשתמש בו; אחרת חופשי
if year_range:
    year = st.number_input(
        f"שנת ייצור (טווח לפי המילון: {year_range[0]}–{year_range[1]}):",
        min_value=year_range[0], max_value=year_range[1], step=1
    )
else:
    year = st.number_input("שנת ייצור:", min_value=1960, max_value=2025, step=1)

# Fuel & Transmission
col1, col2 = st.columns(2)
with col1:
    fuel_type = st.selectbox("סוג דלק:", ["בנזין", "דיזל", "היברידי", "חשמלי", "אחר"])
with col2:
    transmission = st.selectbox("תיבת הילוכים:", ["אוטומטית", "ידנית"])

st.markdown("---")

# ==== Run check ====
if st.button("בדוק אמינות"):
    if not selected_make or not selected_model:
        st.error("יש להזין שם יצרן ודגם תקינים.")
        st.stop()

    # חישוב מגבלות
    df_all = sheet_to_df()
    ok_global, total_global = within_daily_global_limit(df_all, limit=1000)
    ok_user, total_user = within_daily_user_limit(df_all, user_id=current_user, limit=5)

    if not ok_global:
        st.error(f"❌ חציתם את מגבלת 1000 הבדיקות היומיות לכלל המערכת (כבר בוצעו {total_global}). נסו מחר.")
        st.stop()
    if not ok_user:
        st.error(f"❌ הגעת למכסת 5 בדיקות היומית למשתמש ({total_user}/5). נסה מחר.")
        st.stop()

    st.info(f"ניצול יומי – מערכת: {total_global}/1000 | למשתמש: {total_user}/5")
    st.info(f"בודק Cache בשיטס עבור {selected_make} {selected_model} ({year})...")

    # ←← שלב קריטי: אם יש אפילו תוצאה אחת מ־45 הימים האחרונים → מציגים אותה, בלי Gemini
    cached_row, df_all_after = get_cached_from_sheet(selected_make, selected_model, year, max_days=45)
    if cached_row:
        st.success("✅ נמצאה תוצאה בשמורה (≤45 יום). ללא פנייה ל־Gemini.")
        st.subheader(f"ציון אמינות כולל: {int(cached_row.get('base_score',0))}/100")
        if cached_row.get("avg_cost") not in [None, "", "nan"]:
            st.info(f"עלות תחזוקה ממוצעת: כ־{int(float(cached_row.get('avg_cost',0)))} ₪")
        st.write(f"תקלות נפוצות: {cached_row.get('issues','—')}")
        st.write(f"נמצא באמצעות חיפוש אינטרנטי: {cached_row.get('search_performed','false')}")
        st.stop()

    # אין Cache → פונים למודל
    prompt = f"""
    אתה מומחה לאמינות רכבים בישראל עם גישה לחיפוש אינטרנטי.
    חובה לבצע חיפוש עדכני בעברית ובאנגלית ממקורות אמינים בלבד.
    החזר JSON בלבד עם הנתונים הבאים:
    **You must perform an internet search for information sources for the parameters I requested.**
    **You must perform an internet search for repair prices in Israel and Hebrew sources. You can also search for information about faults from international sources, but repair prices are only from Israel.**

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

    רכב: {selected_make} {selected_model} {year}
    סוג דלק: {fuel_type}
    תיבת הילוכים: {transmission}
    כתוב בעברית בלבד.
    """

    try:
        with st.spinner("מבצע חיפוש אינטרנטי ומחשב ציון..."):
            response = model.generate_content(prompt)
            text = (response.text or "").strip()
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                # נסה לתקן JSON "כמעט תקין"
                fixed = repair_json(text)
                parsed = json.loads(fixed)
            else:
                parsed = json.loads(m.group())

        base_score = int(parsed.get("base_score", 0) or 0)
        issues = parsed.get("common_issues", [])
        avg_cost = parsed.get("avg_repair_cost_ILS", 0)
        search_flag = parsed.get("search_performed", False)
        summary = parsed.get("reliability_summary", "אין מידע.")
        detailed_costs = parsed.get("issues_with_costs", [])

        # הצגת תוצאות
        if search_flag:
            st.success("🌐 בוצע חיפוש אינטרנטי בזמן אמת.")
        else:
            st.warning("⚠️ לא בוצע חיפוש אינטרנטי — ייתכן שהמידע חלקי.")

        st.subheader(f"ציון אמינות כולל: {base_score}/100")
        st.write(summary)

        if issues:
            st.markdown("**🔧 תקלות נפוצות:**")
            for i in issues:
                st.markdown(f"- {i}")

        if detailed_costs:
            st.markdown("**💰 עלויות תיקון (אינדיקטיבי):**")
            for item in detailed_costs:
                st.markdown(f"- {item.get('issue','')}: כ־{item.get('avg_cost_ILS', 0)} ₪ (מקור: {item.get('source','')})")

        # שמירה לשיטס
        append_row_to_sheet({
            "date": datetime.date.today().isoformat(),
            "user_id": current_user,
            "make": normalize_text(selected_make),
            "model": normalize_text(selected_model),
            "year": int(year),
            "fuel": fuel_type,
            "transmission": transmission,
            "base_score": base_score,
            "avg_cost": avg_cost,
            "issues": "; ".join(issues) if isinstance(issues, list) else str(issues),
            "search_performed": str(bool(search_flag)).lower()
        })
        st.info("💾 נשמר לשיטס בהצלחה.")

    except Exception as e:
        st.error(f"שגיאה בעיבוד הבקשה: {e}")
