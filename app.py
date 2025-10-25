# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v2.1.0 (Google Sheets Edition)
# בדיקת אמינות רכב לפי יצרן, דגם ושנתון (ישראל)
# Cache חכם (≤45 יום) · מגבלת שימוש · חיפוש אינטרנטי אמיתי
# ===========================================================

import os, json, re, datetime
import pandas as pd
import streamlit as st
from json_repair import repair_json
import google.generativeai as genai

# ==== Streamlit Base ====
st.set_page_config(page_title="🚗 Car Reliability Analyzer", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל")

# ==== Secrets ====
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")

if not GEMINI_API_KEY or not GOOGLE_SHEET_ID or not GOOGLE_CREDENTIALS:
    st.error("⚠️ חסרים Secrets: GEMINI_API_KEY, GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ==== Car Dictionary ====
from car_models_dict import israeli_car_market_full_compilation

# ==== Google Sheets ====
# ==== Google Sheets ====
try:
    import gspread
    from google.oauth2.service_account import Credentials

    # חשוב! להמיר את ה-String ל-Dict
    service_info = json.loads(GOOGLE_CREDENTIALS)

    credentials = Credentials.from_service_account_info(
        service_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    ws = sh.sheet1

    st.success("✅ חיבור ל-Google Sheets הצליח!")

except Exception as e:
    st.error(f"❌ כשל בחיבור לגיליון:")
    st.code(str(e))
    st.stop()


# ==== Helpers ====
def sheet_to_df():
    recs = ws.get_all_records()
    if not recs:
        return pd.DataFrame(columns=["date","user_id","make","model","year","fuel",
                                     "transmission","base_score","avg_cost",
                                     "issues","search_performed"])
    df = pd.DataFrame(recs)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(int)
    return df

def append_to_sheet(rec: dict):
    order = ["date","user_id","make","model","year","fuel","transmission",
             "base_score","avg_cost","issues","search_performed"]
    ws.append_row([rec.get(k,"") for k in order])

def has_daily_limit(df, uid, sys_limit=1000, user_limit=5):
    today = pd.Timestamp.now().date()
    total = len(df[df["date"].dt.date == today])
    user_total = len(df[(df["user_id"]==uid) & (df["date"].dt.date == today)])
    return (total < sys_limit, user_total < user_limit, total, user_total)

def normalize(s): return re.sub(r"\s+"," ",re.sub(r"\(.*?\)","",str(s))).strip().lower()

def get_cached(make, model, year, max_days=45):
    df = sheet_to_df()
    if df.empty: return None, df
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=max_days)
    df = df[df["date"] >= cutoff]

    make = normalize(make)
    model = normalize(model)

    match = df[
        (df["year"]==int(year)) &
        (df["make"].apply(lambda x: normalize(x)==make)) &
        (df["model"].apply(lambda x: normalize(x)==model))
    ]
    if not match.empty:
        return match.iloc[-1].to_dict(), df
    return None, df

# ==== UI ====
email = st.text_input("הכנס אימייל לזיהוי המשתמש:", value=st.session_state.get("email",""))
if email: st.session_state["email"] = email
user_id = st.session_state.get("email","anonymous")

make = st.text_input("יצרן (לדוגמה: Toyota):")
if make in israeli_car_market_full_compilation:
    model = st.selectbox("בחר דגם:", israeli_car_market_full_compilation[make])
else:
    model = st.text_input("דגם:")

year = st.number_input("שנת ייצור:", min_value=1960, max_value=2025, step=1)
fuel = st.selectbox("סוג דלק:", ["בנזין","דיזל","היברידי","חשמלי","אחר"])
trans = st.selectbox("תיבת הילוכים:", ["אוטומטית","ידנית"])

# ==== Submit ====
if st.button("בדוק אמינות"):
    if not make or not model:
        st.error("יש להזין יצרן ודגם")
        st.stop()

    cached, df_all = get_cached(make, model, year)
    ok_sys, ok_user, t_sys, t_user = has_daily_limit(df_all, user_id)

    if not ok_sys: st.error("חריגה ממגבלת 1000 בדיקות יומיות"); st.stop()
    if not ok_user: st.error("חריגה ממגבלת 5 בדיקות יומיות למשתמש"); st.stop()

    if cached:
        st.success("✅ נמצא Cache מ־45 יום 💾")
        st.subheader(f"ציון אמינות: {cached['base_score']}/100")
        st.write(cached["issues"])
        st.stop()

    st.info("⏳ מבצע חיפוש אינטרנטי...")

    prompt = f"""
    אתה מומחה לאמינות רכבים בישראל.
    **חובה לבצע חיפוש אינטרנטי בעברית**.

    החזר אך ורק JSON תקין:
    {{
        "search_performed": true,
        "base_score": 0-100,
        "common_issues": ["עברית"],
        "avg_repair_cost_ILS": מספר,
        "reliability_summary": "בעברית"
    }}

    רכב: {make} {model} {year}
    סוג דלק: {fuel}
    תיבת הילוכים: {trans}
    """

    try:
        res = model.generate_content(prompt)
        text = (res.text or "").strip()
        data = json.loads(repair_json(text))

        append_to_sheet({
            "date": datetime.date.today().isoformat(),
            "user_id": user_id,
            "make": make,
            "model": model,
            "year": int(year),
            "fuel": fuel,
            "transmission": trans,
            "base_score": data.get("base_score", 0),
            "avg_cost": data.get("avg_repair_cost_ILS", 0),
            "issues": "; ".join(data.get("common_issues", [])),
            "search_performed": str(data.get("search_performed", False))
        })

        st.success("✅ חיפוש הושלם")
        st.subheader(f"ציון אמינות: {data.get('base_score', 0)}/100")
        st.write(data.get("reliability_summary","אין מידע"))

    except Exception as e:
        st.error(f"שגיאה: {e}")
