# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v2.3.0 (Sheets Only + Always-On Debug)
# ===========================================================
# מה כלול:
# - חיבור לגוגל שיטס דרך Service Account (מה-Secrets)
# - דיבאג חיבור מפורט שמוצג תמיד על המסך (שלבים, כשל, והסבר איך לתקן)
# - בחירת יצרן/דגם/שנתון עם טווח מהמילון + סוג דלק + תיבת הילוכים
# - Cache בשיטס ל-45 יום:
#     * אם יש אפילו תוצאה אחת עדכנית → מחזירים ישר, בלי מודל
#     * אם יש 3+ תוצאות עדכניות → מציגים ממוצע (יציבות)
# - מגבלות שימוש:
#     * גלובלית: 1000 ליום
#     * למשתמש: מבוטל (anonymous, לפי בחירתך "0")
# - מודל: gemini-2.5-flash
# ===========================================================

import json, re, datetime, difflib, traceback
import pandas as pd
import streamlit as st
from json_repair import repair_json
import google.generativeai as genai

# ====== עיצוב/הגדרות בסיס ======
st.set_page_config(page_title="🚗 Car Reliability Analyzer (Sheets)", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# ====== טעינת Secrets ======
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")  # JSON כמחרוזת

# ====== קונפיג מודל ======
if not GEMINI_API_KEY:
    st.error("⚠️ חסר GEMINI_API_KEY ב-Secrets.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel("gemini-2.5-flash")

# ====== מילון דגמים ======
from car_models_dict import israeli_car_market_full_compilation

# ====== פונקציות עזר ======
def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", str(s))).strip().lower()

def similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def parse_year_range_from_model_label(model_label: str):
    # תומך גם ב"1962-2012, 2023-2025" – ניקח את הטווח הראשון
    m = re.search(r"\((\d{4})\s*-\s*(\d{4})", model_label)
    if m:
        try:
            return int(m.group(1)), int(m.group(2))
        except:
            return None, None
    return None, None

# ====== דיבאג חיבור – מוצג תמיד ======
def _ok(step):    return {"step": step, "status": "✅ OK", "hint": ""}
def _fail(step, why, fix): return {"step": step, "status": f"❌ FAIL - {why}", "hint": fix}

def run_connectivity_diagnostics():
    results = []

    # 1) בדיקת קיום סיקרטים
    if GEMINI_API_KEY:
        results.append(_ok("GEMINI_API_KEY נמצא"))
    else:
        results.append(_fail("GEMINI_API_KEY", "חסר", "יש לשים מפתח ב־Secrets בשם GEMINI_API_KEY"))
    if GOOGLE_SHEET_ID:
        results.append(_ok("GOOGLE_SHEET_ID נמצא"))
    else:
        results.append(_fail(
            "GOOGLE_SHEET_ID", "חסר",
            "העתק את ה-ID מה־URL של הגיליון (החלק שבין /d/ ל-/edit) ושמור ב-Secrets."
        ))
    if GOOGLE_SERVICE_ACCOUNT_JSON:
        results.append(_ok("GOOGLE_SERVICE_ACCOUNT_JSON נמצא"))
    else:
        results.append(_fail(
            "GOOGLE_SERVICE_ACCOUNT_JSON", "חסר",
            "הדבק את קובץ ה־Service Account JSON כולו בין שלושה מרכאות משולשות ב-Secrets."
        ))
        return results, None, None, None  # אין טעם להמשיך

    # 2) JSON של Service Account
    try:
        service_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        results.append(_ok("פרסינג JSON של Service Account"))
    except Exception as e:
        results.append(_fail(
            "פרסינג JSON של Service Account", "JSON לא תקין",
            f"ודא שהטקסט ב־Secrets הוא JSON מלא (לא TOML). שגיאה:\n{repr(e)}"
        ))
        return results, None, None, None

    # תיקון אוטומטי לשבירות מפתח עם \\n
    try:
        if "private_key" in service_info and "\\n" in service_info["private_key"]:
            service_info["private_key"] = service_info["private_key"].replace("\\n", "\n")
    except Exception:
        pass

    # 3) מפתחות חובה קיימים
    required_keys = ["type","project_id","private_key_id","private_key","client_email","client_id","token_uri"]
    missing = [k for k in required_keys if k not in service_info]
    if missing:
        results.append(_fail(
            "בדיקת שדות חובה ב-JSON", f"חסרים: {', '.join(missing)}",
            "ייצא מחדש את המפתח ב־GCP (IAM & Admin → Service Accounts → Keys → Add Key → Create new key (JSON))."
        ))
        return results, None, None, None
    else:
        results.append(_ok("שדות חובה קיימים ב-JSON"))

    # 4) יצירת Credentials
    try:
        from google.oauth2.service_account import Credentials
        credentials = Credentials.from_service_account_info(
            service_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        results.append(_ok("יצירת Credentials מה־JSON"))
    except Exception as e:
        results.append(_fail(
            "יצירת Credentials", "נכשל",
            f"בדוק את private_key ושהוא כולל BEGIN/END. שגיאה:\n{repr(e)}"
        ))
        return results, None, None, None

    # 5) התחברות gspread
    try:
        import gspread
        gc = gspread.authorize(credentials)
        results.append(_ok("אימות gspread"))
    except Exception as e:
        results.append(_fail(
            "authorize(gspread)", "נכשל",
            f"ודא שה־scope נכון ושלא חסומות הרשאות. שגיאה:\n{repr(e)}"
        ))
        return results, None, None, None

    # 6) פתיחת הגיליון לפי ID
    try:
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        results.append(_ok(f"פתיחת גיליון לפי ID ({GOOGLE_SHEET_ID})"))
    except Exception as e:
        results.append(_fail(
            "פתיחת גיליון לפי ID", "נכשל",
            "שתף את הגיליון עם כתובת ה־client_email שב־Service Account (Viewer/Editor). "
            f"client_email: {service_info.get('client_email','(לא ידוע)')}\n"
            f"שגיאה: {repr(e)}"
        ))
        return results, None, None, None

    # 7) worksheet ראשון
    try:
        ws = sh.sheet1
        results.append(_ok("גישה ל־sheet1"))
    except Exception as e:
        results.append(_fail(
            "גישה ל־sheet1", "נכשל",
            f"ודא שקיים worksheet ראשון. שגיאה:\n{repr(e)}"
        ))
        return results, sh, None, None

    # 8) כותרות חובה
    try:
        headers = [
            "date","user_id","make","model","year","fuel","transmission",
            "base_score","avg_cost","issues","search_performed"
        ]
        current = ws.row_values(1)
        if [h.lower() for h in current] != headers:
            ws.update("A1", [headers])
        results.append(_ok("וידוא כותרות בגיליון"))
    except Exception as e:
        results.append(_fail(
            "עדכון כותרות בגיליון", "נכשל",
            f"בדוק הרשאות עריכה (Editor) לשירות. שגיאה:\n{repr(e)}"
        ))
        # עדיין נחזיר את ws להמשך ניסוי
        return results, sh, ws, gc

    return results, sh, ws, gc

# ====== מריצים דיאגנוסטיקה תמיד ומציגים ======
diag_results, sh, ws, gc = run_connectivity_diagnostics()
st.markdown("### 🧪 דיאגנוסטיקה לחיבור Google Sheets (מוצג תמיד)")
for r in diag_results:
    st.markdown(f"- **{r['step']}** → {r['status']}")
    if r["hint"]:
        with st.expander("איך לתקן / הסבר", expanded=False):
            st.write(r["hint"])

# אם אין חיבור שמיש ל־ws – אין טעם להמשיך
if ws is None:
    st.error("❌ אין חיבור שמיש ל־Google Sheets. תקן לפי ההנחיות למעלה ורענן.")
    st.stop()

# ====== I/O מול הגיליון ======
def sheet_to_df() -> pd.DataFrame:
    try:
        recs = ws.get_all_records()
    except Exception as e:
        st.error("❌ כשל בקריאת נתונים מהגיליון")
        st.code(repr(e))
        return pd.DataFrame(columns=[
            "date","user_id","make","model","year","fuel","transmission",
            "base_score","avg_cost","issues","search_performed"
        ])

    if not recs:
        return pd.DataFrame(columns=[
            "date","user_id","make","model","year","fuel","transmission",
            "base_score","avg_cost","issues","search_performed"
        ])

    df = pd.DataFrame(recs)
    # טיפוסים
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["make","model","fuel","transmission","issues","user_id","search_performed"]:
        if c in df.columns:
            df[c] = df[c].astype(str).fillna("")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(int)
    if "base_score" in df.columns:
        df["base_score"] = pd.to_numeric(df["base_score"], errors="coerce")
    if "avg_cost" in df.columns:
        df["avg_cost"] = pd.to_numeric(df["avg_cost"], errors="coerce")
    return df

def append_row_to_sheet(row_dict: dict):
    order = ["date","user_id","make","model","year","fuel","transmission",
             "base_score","avg_cost","issues","search_performed"]
    row = [row_dict.get(k,"") for k in order]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error("❌ כשל בכתיבה לשיטס")
        st.code(repr(e))

# ====== מגבלות שימוש ======
GLOBAL_DAILY_LIMIT = 1000
USER_DAILY_LIMIT = 0   # לפי בקשתך: 0 = ללא מגבלת משתמש (כולם anonymous)

def within_daily_global_limit(df: pd.DataFrame, limit=GLOBAL_DAILY_LIMIT):
    today = pd.Timestamp.now().date()
    df_today = df[df["date"].dt.date == today] if "date" in df.columns else pd.DataFrame()
    return (len(df_today) < limit, len(df_today))

def within_daily_user_limit(df: pd.DataFrame, user_id: str, limit=USER_DAILY_LIMIT):
    if limit <= 0:
        return True, 0
    today = pd.Timestamp.now().date()
    user_today = df[(df["user_id"].str.lower()==str(user_id).lower()) & (df["date"].dt.date == today)] if "date" in df.columns else pd.DataFrame()
    return (len(user_today) < limit, len(user_today))

# ====== Cache חכם: אם יש לפחות אחת ב-45 ימים → מחזירים; אם 3+ → ממוצע ======
def get_cached_from_sheet(make: str, model: str, year: int, max_days=45):
    df = sheet_to_df()
    if df.empty:
        return None, df

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=max_days)
    recent = df[df["date"] >= cutoff]

    make_clean = normalize_text(make)
    model_clean = normalize_text(model)

    # התאמה חזקה תחילה (>=0.95), ואז רכה (>=0.90)
    hits = pd.DataFrame()
    for th in [0.95, 0.90]:
        cand = recent[
            (recent["year"] == int(year)) &
            (recent["make"].apply(lambda x: similar(x, make_clean) >= th)) &
            (recent["model"].apply(lambda x: similar(x, model_clean) >= th))
        ]
        if not cand.empty:
            hits = cand.sort_values("date")
            break

    if hits.empty:
        return None, df

    # אם יש 3+ תוצאות → נחזיר ממוצע (ליציבות)
    if len(hits) >= 3:
        avg_score = float(hits["base_score"].dropna().mean()) if "base_score" in hits else None
        avg_cost  = float(hits["avg_cost"].dropna().mean()) if "avg_cost" in hits else None
        issues_agg = "; ".join([str(x) for x in hits["issues"].astype(str).tail(3)])  # אחרונות לתצוגה
        return {
            "is_aggregate": True,
            "count": len(hits),
            "base_score": round(avg_score) if avg_score is not None else None,
            "avg_cost": round(avg_cost) if avg_cost is not None else None,
            "issues": issues_agg,
            "search_performed": "true (history aggregate)",
            "last_date": hits.iloc[-1]["date"]
        }, df

    # אחרת נחזיר את העדכנית ביותר
    row = hits.iloc[-1].to_dict()
    row["is_aggregate"] = False
    row["count"] = len(hits)
    return row, df

# ====== UI בחירה ======
st.markdown("### 🔍 בחירת יצרן, דגם ושנתון")
make_list = sorted(israeli_car_market_full_compilation.keys())
make_choice = st.selectbox("בחר יצרן מהרשימה:", ["בחר..."] + make_list, index=0)
make_input  = st.text_input("או הזן שם יצרן ידנית:")

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
    model_input  = st.text_input("או הזן דגם ידנית:")
    if model_choice != "בחר דגם...":
        selected_model = model_choice
    elif model_input.strip():
        selected_model = model_input.strip()

    if selected_model:
        yr_start, yr_end = parse_year_range_from_model_label(selected_model)
        if yr_start and yr_end:
            year_range = (yr_start, yr_end)
else:
    if selected_make:
        st.warning("️📋 יצרן לא במילון – הזן דגם ידנית:")
    selected_model = st.text_input("שם דגם:")

# שנתון
if year_range:
    year = st.number_input(
        f"שנת ייצור (טווח לפי המילון: {year_range[0]}–{year_range[1]}):",
        min_value=year_range[0], max_value=year_range[1], step=1
    )
else:
    year = st.number_input("שנת ייצור:", min_value=1960, max_value=2025, step=1)

# דלק/תיבה
col1, col2 = st.columns(2)
with col1:
    fuel_type = st.selectbox("סוג דלק:", ["בנזין", "דיזל", "היברידי", "חשמלי", "אחר"])
with col2:
    transmission = st.selectbox("תיבת הילוכים:", ["אוטומטית", "ידנית"])

st.markdown("---")

# ====== הפעלה ======
if st.button("בדוק אמינות"):
    # זיהוי משתמש: לפי בחירתך – כולם anonymous
    current_user = "anonymous"

    if not selected_make or not selected_model:
        st.error("יש להזין שם יצרן ודגם תקינים.")
        st.stop()

    # מגבלות יומיות
    df_all = sheet_to_df()
    ok_global, total_global = within_daily_global_limit(df_all, limit=GLOBAL_DAILY_LIMIT)
    ok_user, total_user     = within_daily_user_limit(df_all, user_id=current_user, limit=USER_DAILY_LIMIT)

    if not ok_global:
        st.error(f"❌ חציתם את מגבלת {GLOBAL_DAILY_LIMIT} הבדיקות היומיות לכלל המערכת (כבר בוצעו {total_global}). נסו מחר.")
        st.stop()
    if not ok_user:
        st.error(f"❌ הגעת למכסת היומית למשתמש ({total_user}/{USER_DAILY_LIMIT}). נסה מחר.")
        st.stop()

    st.info(f"ניצול יומי – מערכת: {total_global}/{GLOBAL_DAILY_LIMIT} | למשתמש: {'ללא מגבלה'}")

    st.info(f"בודק Cache בשיטס עבור {selected_make} {selected_model} ({year})...")
    cached_row, df_all_after = get_cached_from_sheet(selected_make, selected_model, int(year), max_days=45)

    # אם קיימת אפילו תוצאה אחת עדכנית → מציגים מייד
    if cached_row:
        if cached_row.get("is_aggregate"):
            st.success(f"✅ נמצאו {cached_row['count']} תוצאות עדכניות (≤45 יום). מוצג ממוצע יציב. אין פנייה ל־Gemini.")
            if cached_row.get("base_score") is not None:
                st.subheader(f"ציון אמינות כולל (ממוצע): {int(cached_row['base_score'])}/100")
            if cached_row.get("avg_cost") is not None:
                st.info(f"עלות תחזוקה ממוצעת (ממוצע): כ־{int(float(cached_row['avg_cost']))} ₪")
            st.write(f"תקלות נפוצות (שלוש האחרונות): {cached_row.get('issues','—')}")
            st.write(f"נמצא באמצעות חיפוש אינטרנטי: {cached_row.get('search_performed','false')}")
            st.stop()
        else:
            st.success("✅ נמצאה תוצאה שמורה מ־45 הימים האחרונים. ללא פנייה ל־Gemini.")
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

    רכב: {selected_make} {selected_model} {int(year)}
    סוג דלק: {fuel_type}
    תיבת הילוכים: {transmission}
    כתוב בעברית בלבד.
    """.strip()

    try:
        with st.spinner("מבצע חיפוש אינטרנטי ומחשב ציון..."):
            resp = llm.generate_content(prompt)
            raw = (getattr(resp, "text", "") or "").strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
            else:
                # ניסיון תיקון JSON "כמעט תקין"
                fixed = repair_json(raw)
                parsed = json.loads(fixed)

        base_score = int(parsed.get("base_score", 0) or 0)
        issues = parsed.get("common_issues", [])
        avg_cost = parsed.get("avg_repair_cost_ILS", 0)
        search_flag = parsed.get("search_performed", False)
        summary = parsed.get("reliability_summary", "אין מידע.")
        detailed_costs = parsed.get("issues_with_costs", [])

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

        # שמירה לשיטס (תמיד normalize לשמות)
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
            "issues": "; ".join(issues) if isinstance(issues, list) else str(issues),
            "search_performed": str(bool(search_flag)).lower()
        })
        st.info("💾 נשמר לשיטס בהצלחה.")

    except Exception as e:
        st.error("שגיאה בעיבוד הבקשה:")
        st.code(repr(e))
        st.code(traceback.format_exc())
