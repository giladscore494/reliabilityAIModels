# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v2.5.0 (Sheets + Always-On Debug)
# ===========================================================
# שדרוגים:
# ✅ Drive scope - מאפשר open_by_key ללא PermissionError
# ✅ דיאגנוסטיקה מתקדמת (403/permissions)
# ✅ prompt ארוז בפונקציה – אין יותר שבירת מרכאות
# ===========================================================

import json, re, datetime, difflib, traceback
import pandas as pd
import streamlit as st
from json_repair import repair_json
import google.generativeai as genai

# ====== עיצוב ======
st.set_page_config(page_title="🚗 Car Reliability Analyzer (Sheets)", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# ====== Secrets ======
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# ====== בדיקת API ======
if not GEMINI_API_KEY:
    st.error("⚠️ חסר GEMINI_API_KEY ב-Secrets")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel("gemini-2.5-flash")

# ====== מילון דגמים ======
from car_models_dict import israeli_car_market_full_compilation

# ====== פונקציות עזר ======
def normalize_text(s): return re.sub(r"\s+", " ", s.lower().strip()) if s else ""
def similar(a,b): return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def parse_year_range_from_model_label(x):
    m = re.search(r"\((\d{4})\s*-\s*(\d{4})", str(x))
    return (int(m.group(1)), int(m.group(2))) if m else (None,None)

# ====== prompt ארוז באופן בטוח ======
def build_prompt(make, model, year, fuel_type, transmission):
    return f"""
אתה מומחה לאמינות רכבים בישראל עם גישה לחיפוש אינטרנטי.
חובה לבצע חיפוש עדכני בעברית ובאנגלית ממקורות אמינים בלבד.
החזר JSON בלבד עם הנתונים הבאים:

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

🧮 משקלות:
- מנוע/גיר 35%
- חשמל ואלקטרוניקה 20%
- מתלים/בלמים 10%
- עלות תחזוקה 15%
- שביעות רצון 15%
- ריקולים 5%

רכב: {make} {model} {int(year)}
דלק: {fuel_type}
תיבה: {transmission}
כתוב בעברית בלבד.
""".strip()

# ====== דיאגנוסטיקה ======
def _ok(step): return {"step":step, "status":"✅ OK", "hint":""}
def _fail(step, why, fix): return {"step":step, "status":f"❌ FAIL - {why}", "hint":fix}

def run_connectivity_diagnostics():
    results=[]

    # סיקרטים
    if GEMINI_API_KEY: results.append(_ok("GEMINI_API_KEY"))
    if GOOGLE_SHEET_ID: results.append(_ok("GOOGLE_SHEET_ID"))
    if GOOGLE_SERVICE_ACCOUNT_JSON: results.append(_ok("GOOGLE_SERVICE_ACCOUNT_JSON"))
    else:
        results.append(_fail("Service JSON","Missing","הדבק ב-Secrets"))
        return results,None,None,None

    # Parse JSON
    try:
        info=json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        results.append(_ok("Parsing JSON"))
        if "\\n" in info.get("private_key",""):
            info["private_key"]=info["private_key"].replace("\\n","\n")
    except:
        results.append(_fail("JSON","Invalid","בדוק מבנה JSON"))
        return results,None,None,None

    # Keys
    required=["type","project_id","private_key_id","private_key","client_email","client_id","token_uri"]
    for k in required:
        if k not in info:
            results.append(_fail("Service JSON","Missing fields","ייצא JSON חדש מחשבון GCP"))
            return results,None,None,None
    results.append(_ok("Required JSON Keys"))

    # Credentials + authorize
    try:
        from google.oauth2.service_account import Credentials
        import gspread
        credentials=Credentials.from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        gc=gspread.authorize(credentials)
        results.append(_ok("gspread Auth"))
    except Exception as e:
        results.append(_fail("auth","credentials fail",repr(e)))
        return results,None,None,None

    # open_by_key
    try:
        sh=gc.open_by_key(GOOGLE_SHEET_ID)
        results.append(_ok("Open Sheet ID"))
    except Exception as e:
        results.append(_fail(
            "Open Sheet ID","PermissionError",
            "🚫 שתף את הגיליון עם ה־client_email + Editor\n" +
            f"client_email: {info.get('client_email')}\nשגיאה: {repr(e)}"
        ))
        return results,None,None,None

    # sheet1
    try:
        ws=sh.sheet1
        results.append(_ok("Access sheet1"))
    except:
        results.append(_fail("sheet1","missing","צור sheet ראשון"))
        return results,sh,None,None

    # headers
    headers=["date","user_id","make","model","year","fuel","transmission","base_score","avg_cost","issues","search_performed"]
    try:
        current=ws.row_values(1)
        if [c.lower() for c in current]!=headers:
            ws.update("A1",[headers])
        results.append(_ok("Headers OK"))
    except Exception as e:
        results.append(_fail("Headers","write fail",repr(e)))

    return results,sh,ws,gc

# ====== הצגת דיאגנוסטיקה ======
diag_results,sh,ws,gc = run_connectivity_diagnostics()
st.markdown("### 🧪 דיאגנוסטיקה")
for r in diag_results:
    st.write(f"- **{r['step']}** → {r['status']}")
    if r["hint"]:
        st.info(r["hint"])

if ws is None: st.stop()

# ====== Sheet I/O ======
def sheet_to_df():
    try: recs=ws.get_all_records()
    except: return pd.DataFrame()
    return pd.DataFrame(recs) if recs else pd.DataFrame()

def append_row(row_dict):
    order=["date","user_id","make","model","year","fuel","transmission","base_score","avg_cost","issues","search_performed"]
    row=[row_dict.get(k,"") for k in order]
    try: ws.append_row(row,value_input_option="USER_ENTERED")
    except Exception as e: st.error(repr(e))

# ====== מגבלות ======
GLOBAL_DAILY_LIMIT=1000
USER_DAILY_LIMIT=0

def within_daily_global(df):
    today=pd.Timestamp.now().date()
    total=len(df[df["date"]==str(today)]) if "date" in df else 0
    return (total<GLOBAL_DAILY_LIMIT,total)

# ====== Cache ======
def get_cached(make,model,year):
    df=sheet_to_df()
    if df.empty: return None,df
    recent=df[pd.to_datetime(df["date"])>=pd.Timestamp.now()-pd.Timedelta(days=45)]
    make_n,model_n=normalize_text(make),normalize_text(model)

    for th in [0.95,0.90]:
        hits=recent[
            (recent["year"]==int(year)) &
            (recent["make"].apply(lambda x:similar(x,make_n)>=th)) &
            (recent["model"].apply(lambda x:similar(x,model_n)>=th))
        ]
        if not hits.empty:
            hits=hits.sort_values("date")
            return hits.iloc[-1].to_dict(),df
    return None,df

# ====== UI ======
st.markdown("### 🔍 בחירת רכב")
make_list=sorted(israeli_car_market_full_compilation.keys())
make=st.selectbox("יצרן:",["בחר..."]+make_list)
if make=="בחר...": make=""

model,year_range="",None
if make:
    models=israeli_car_market_full_compilation[make]
    model=st.selectbox("דגם:",["בחר דגם..."]+models)
    if model=="בחר דגם...": model=""
    if model:
        ys,ye=parse_year_range_from_model_label(model)
        if ys and ye: year_range=(ys,ye)

year=st.number_input("שנת ייצור:", min_value=1960,max_value=2025,
                     value=year_range[0] if year_range else 2020)

fuel=st.selectbox("דלק:",["בנזין","דיזל","היברידי","חשמלי","אחר"])
trans=st.selectbox("תיבה:",["אוטומטית","ידנית"])

# ====== כפתור ======
if st.button("בדוק אמינות"):

    if not make or not model:
        st.error("חסר יצרן/דגם")
        st.stop()

    df=sheet_to_df()
    ok_global,total=within_daily_global(df)
    if not ok_global:
        st.error("חריגה ממגבלה יומית")
        st.stop()

    # Cache
    cached,_=get_cached(make,model,year)
    if cached:
        st.success("✅ נתון מה־Cache")
        st.write(cached)
        st.stop()

    prompt=build_prompt(make,model,year,fuel,trans)

    with st.spinner("שואל את Gemini..."):
        try:
            resp=llm.generate_content(prompt)
            raw=(resp.text or "").strip()
            m=re.search(r"\{.*\}",raw,re.DOTALL)
            parsed=json.loads(m.group() if m else repair_json(raw))
        except Exception as e:
            st.error("🌐 בעיית ניתוח תשובה")
            st.code(repr(e))
            st.stop()

    base=int(parsed.get("base_score",0))
    avg_cost=parsed.get("avg_repair_cost_ILS",0)
    issues=parsed.get("common_issues",[])
    search_flag=parsed.get("search_performed",False)
    summary=parsed.get("reliability_summary","אין מידע")

    st.subheader(f"🔧 ציון אמינות: {base}/100")
    st.write(summary)
    if issues:
        st.write("תקלות נפוצות:")
        for x in issues: st.markdown(f"- {x}")

    append_row({
        "date": str(datetime.date.today()),
        "user_id": "anonymous",
        "make": make,
        "model": model,
        "year": int(year),
        "fuel": fuel,
        "transmission": trans,
        "base_score": base,
        "avg_cost": avg_cost,
        "issues": "; ".join(issues),
        "search_performed": str(search_flag).lower()
    })
    st.info("✅ נשמר לשיטס")