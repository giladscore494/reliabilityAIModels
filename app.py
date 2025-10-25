# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v2.0.1 (Sheets Fixed)
# Google Sheets Cache · Smart Filter · Daily Limits · Fuel/Transmission
# ===========================================================

import os, json, re, datetime
import pandas as pd
import streamlit as st
import difflib
from json_repair import repair_json
import google.generativeai as genai

# ==== Streamlit base ====
st.set_page_config(page_title="🚗 Car Reliability Analyzer", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# ==== Secrets ====
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")

if not GEMINI_API_KEY or not GOOGLE_SHEET_ID or not GOOGLE_CREDENTIALS:
    st.error("⚠️ חסרים Secrets: GEMINI_API_KEY, GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ==== Car dictionary ====
from car_models_dict import israeli_car_market_full_compilation

# ==== Connect Google Sheets ====
try:
    import gspread
    from google.oauth2.service_account import Credentials

    st.write("🔄 מנסה להתחבר ל-Google Sheets...")

    creds = Credentials.from_service_account_info(
        GOOGLE_CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    ws = sh.sheet1  # ✅ תיקון פה

    st.success("✅ חיבור ל-Google Sheets הצליח!")
except Exception as e:
    st.error("❌ כשל חיבור ל-Google Sheets:")
    st.code(str(e))
    st.stop()

# ==== User ID Input (Simple) ====
def get_current_user_id():
    st.markdown("#### התחברות (לזהות את מכסת הבדיקות שלך)")
    email = st.text_input("הזן אימייל (ללא סיסמה):", value=st.session_state.get("user_email", ""))
    if email:
        st.session_state["user_email"] = email.strip().lower()
    return st.session_state.get("user_email", "anonymous")

current_user = get_current_user_id()

# ==== Helper Functions ====
def normalize_text(s):
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", str(s))).strip().lower()

def similar(a, b):
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def sheet_to_df():
    recs = ws.get_all_records()
    if not recs:
        return pd.DataFrame(columns=[
            "date","user_id","make","model","year","fuel","transmission",
            "base_score","avg_cost","issues","search_performed"
        ])
    df = pd.DataFrame(recs)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["year"] = pd.to_numeric(df.get("year", 0), errors="coerce").fillna(0).astype(int)
    return df

def append_row_to_sheet(row_dict):
    order = ["date","user_id","make","model","year","fuel","transmission",
             "base_score","avg_cost","issues","search_performed"]
    row = [row_dict.get(k, "") for k in order]
    ws.append_row(row, value_input_option="USER_ENTERED")

def get_cached_from_sheet(make, model, year, days=45):
    df = sheet_to_df()
    if df.empty:
        return None, df
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    recent = df[df["date"] >= cutoff]
    make_clean = normalize_text(make)
    model_clean = normalize_text(model)
    for th in [0.95, 0.90]:
        matches = recent[
            (recent["year"] == int(year)) &
            (recent["make"].apply(lambda x: similar(x, make_clean) >= th)) &
            (recent["model"].apply(lambda x: similar(x, model_clean) >= th))
        ]
        if not matches.empty:
            return matches.sort_values("date").iloc[-1].to_dict(), df
    return None, df

# ==== Select Car ====
st.markdown("### 🔍 בחירת רכב")

make_list = sorted(israeli_car_market_full_compilation.keys())
make_sel = st.selectbox("יצרן:", ["בחר..."] + make_list)
make_input = st.text_input("או הזן יצרן:")

selected_make = make_sel if make_sel != "בחר..." else make_input.strip()

model_sel = st.selectbox("דגם:", ["בחר דגם..."] + israeli_car_market_full_compilation.get(selected_make, []))
model_input = st.text_input("או הזן דגם:")

selected_model = model_sel if model_sel != "בחר דגם..." else model_input.strip()

year = st.number_input("שנת ייצור:", min_value=1960, max_value=2025, step=1)

fuel = st.selectbox("דלק:", ["בנזין","דיזל","היברידי","חשמלי","אחר"])
transmission = st.selectbox("גיר:", ["אוטומטית","ידנית"])

st.markdown("---")

# ==== Run Check ====
if st.button("בדוק אמינות"):
    if not selected_make or not selected_model:
        st.error("❌ נא לבחור יצרן ודגם")
        st.stop()

    df_all = sheet_to_df()
    cached, df_all = get_cached_from_sheet(selected_make, selected_model, year)

    # ✅ Cache Hit → Skip Gemini
    if cached:
        st.success("✅ נמצא ב-Cache (≤45 יום)")
        st.subheader(f"ציון אמינות: {cached['base_score']}/100")
        st.write(f"תקלות נפוצות: {cached['issues']}")
        st.write(f"עלות ממוצעת: {cached['avg_cost']} ₪")
        st.stop()

    prompt = f"""
    אתה מומחה לאמינות רכבים בישראל עם חיפוש אינטרנטי.
    החזר JSON בלבד:

    {{
      "search_performed": true או false,
      "base_score": מספר בין 0 ל-100,
      "common_issues": [תקלות בעברית],
      "avg_repair_cost_ILS": מספר,
      "reliability_summary": "..."
    }}

    רכב: {selected_make} {selected_model} {year}
    דלק: {fuel}
    גיר: {transmission}
    """

    response = model.generate_content(prompt)
    text = response.text
    json_text = re.search(r"\{.*\}", text, re.DOTALL)
    parsed = json.loads(json_text.group()) if json_text else json.loads(repair_json(text))

    base_score = parsed.get("base_score", 0)
    issues = parsed.get("common_issues", [])
    avg_cost = parsed.get("avg_repair_cost_ILS", 0)

    st.subheader(f"ציון אמינות כולל: {base_score}/100")
    for i in issues:
        st.markdown(f"- {i}")

    append_row_to_sheet({
        "date": datetime.date.today().isoformat(),
        "user_id": current_user,
        "make": normalize_text(selected_make),
        "model": normalize_text(selected_model),
        "year": int(year),
        "fuel": fuel,
        "transmission": transmission,
        "base_score": base_score,
        "avg_cost": avg_cost,
        "issues": "; ".join(issues),
        "search_performed": "true"
    })

    st.info("💾 נשמר בגוגל שיטס")
