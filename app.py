# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v1.4
# ניתוח אמינות רכב לפי יצרן, דגם ושנתון עם חיפוש אינטרנטי
# כולל:
# - Cache של 45 יום (לא שולח שוב לאותו רכב)
# - עדכון מילון אוטומטי
# - שמירה ל־GitHub (CSV + Dict)
# - הגבלת בקשות יומית (1000 כלליות / 5 למשתמש)
# ===========================================================

import os, json, re, uuid, datetime
import pandas as pd
import streamlit as st
from github import Github
from json_repair import repair_json
import google.generativeai as genai

# -----------------------------------------------------------
# הגדרות בסיסיות
# -----------------------------------------------------------
st.set_page_config(page_title="🚗 Car Reliability Analyzer", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל")

# -----------------------------------------------------------
# טעינת מפתחות (Secrets)
# -----------------------------------------------------------
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
GITHUB_REPO = st.secrets.get("GITHUB_REPO")

if not GEMINI_API_KEY or not GITHUB_TOKEN or not GITHUB_REPO:
    st.error("⚠️ חסרים מפתחות Secrets (GEMINI_API_KEY, GITHUB_TOKEN, GITHUB_REPO).")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# -----------------------------------------------------------
# זיהוי משתמש (UUID)
# -----------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())
user_id = st.session_state["user_id"]

# -----------------------------------------------------------
# טעינת מילון יצרנים ודגמים
# -----------------------------------------------------------
from car_models_dict import israeli_car_market_full_compilation

# -----------------------------------------------------------
# הגדרות קובץ GitHub
# -----------------------------------------------------------
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)
csv_path = "reliability_results.csv"

# -----------------------------------------------------------
# טעינת / יצירת קובץ CSV
# -----------------------------------------------------------
try:
    contents = repo.get_contents(csv_path)
    df = pd.read_csv(contents.download_url)
except Exception:
    df = pd.DataFrame(columns=[
        "date", "user_id", "make", "model", "year",
        "base_score", "avg_cost", "issues", "search_performed"
    ])
    repo.create_file(csv_path, "init reliability results", df.to_csv(index=False))

# -----------------------------------------------------------
# מגבלות יומיות
# -----------------------------------------------------------
today = datetime.date.today().isoformat()
daily_limit_global = 1000
daily_limit_user = 5

today_df = df[df["date"] == today]
if len(today_df) >= daily_limit_global:
    st.error("🚫 הגעת למכסה היומית של 1000 בקשות. נסה שוב מחר.")
    st.stop()

user_today_df = today_df[today_df["user_id"] == user_id]
if len(user_today_df) >= daily_limit_user:
    st.warning("⚠️ הגעת למכסה האישית (5 בקשות ליום). נסה שוב מחר.")
    st.stop()

# -----------------------------------------------------------
# ממשק משתמש – בחירת יצרן ודגם
# -----------------------------------------------------------
make_list = sorted(israeli_car_market_full_compilation.keys())
st.markdown("### 🔍 בחר יצרן ודגם לבדיקה")

make_choice = st.selectbox("בחר יצרן:", ["בחר..."] + make_list)
selected_make, selected_model = None, None

if make_choice != "בחר...":
    models = israeli_car_market_full_compilation.get(make_choice, [])
    if models:
        model_choice = st.selectbox(f"בחר דגם של {make_choice}:", ["בחר דגם..."] + models)
        if model_choice != "בחר דגם...":
            selected_make = make_choice
            selected_model = model_choice
    else:
        st.warning("לא נמצאו דגמים לחברה זו. הזן ידנית:")
        selected_make = st.text_input("שם חברה:")
        selected_model = st.text_input("שם דגם:")
else:
    st.warning("שם החברה והדגם לא מופיעים במערכת. יש להזין ידנית:")
    selected_make = st.text_input("שם חברה:")
    selected_model = st.text_input("שם דגם:")

year = st.number_input("שנת ייצור:", min_value=2000, max_value=2025, step=1)

# -----------------------------------------------------------
# Cache – בדיקה אם יש תוצאה עדכנית (≤45 יום)
# -----------------------------------------------------------
def get_cached(make, model, year):
    window = datetime.date.today() - datetime.timedelta(days=45)
    cached = df[
        (df["make"].str.lower() == make.lower()) &
        (df["model"].str.lower() == model.lower()) &
        (df["year"] == year) &
        (pd.to_datetime(df["date"]) >= pd.Timestamp(window))
    ]
    return cached.iloc[-1] if not cached.empty else None

# -----------------------------------------------------------
# הפעלת בדיקה
# -----------------------------------------------------------
if st.button("בדוק אמינות"):
    if not selected_make or not selected_model:
        st.error("יש להזין שם חברה ודגם תקינים.")
        st.stop()

    cached_row = get_cached(selected_make, selected_model, year)
    if cached_row is not None:
        st.success(f"⚡ נמצאה תוצאה ממאגר ({cached_row['date']}) – לא נשלחה בקשה חדשה.")
        st.subheader(f"ציון אמינות: {cached_row['base_score']}/100")
        st.write(f"עלות ממוצעת: ₪{cached_row['avg_cost']}")
        st.markdown("**🔧 תקלות נפוצות:**")
        for issue in cached_row["issues"].split("; "):
            st.markdown(f"- {issue}")
        if cached_row["search_performed"]:
            st.info("🌐 בוצע חיפוש אינטרנטי בזמן יצירת הנתון.")
        st.stop()

    # -------------------------------------------------------
    # יצירת Prompt חכם
    # -------------------------------------------------------
    st.info(f"מתבצעת בדיקת אמינות עבור {selected_make} {selected_model} ({year})...")

    prompt = f"""
    אתה פועל כחוקר אמינות רכבים בישראל עם גישה מלאה לחיפוש אינטרנטי.
    חובה לבצע חיפוש בזמן אמת בעברית ובאנגלית ממקורות אמינים בלבד.
    החזר פלט JSON עם ציון אמינות, תקלות נפוצות, עלויות תיקון, ודיווח אם בוצע חיפוש.

    נושא הבדיקה:
    יצרן: {selected_make}
    דגם: {selected_model}
    שנת ייצור: {year}

    ✳️ החזר JSON תקני בלבד במבנה הבא:
    {{
        "search_performed": true או false,
        "base_score": מספר בין 0 ל-100,
        "common_issues": [תקלות נפוצות בעברית],
        "avg_repair_cost_ILS": מספר ממוצע,
        "issues_with_costs": [
            {{
                "issue": "שם התקלה בעברית",
                "avg_cost_ILS": מספר,
                "source": "מקור"
            }}
        ],
        "reliability_summary": "סיכום בעברית על רמת האמינות",
        "sources": ["רשימת אתרים ששימשו"]
    }}

    🧮 משקלות ציון אמינות:
    - מנוע/גיר/מערכת היברידית – 35%
    - חשמל ואלקטרוניקה – 20%
    - מתלים/בלמים/צמיגים – 10%
    - עלות תחזוקה וחלקים – 15%
    - שביעות רצון בעלי רכב – 15%
    - ריקולים ובטיחות – 5%

    כתוב בעברית בלבד ואל תכלול טקסט נוסף מחוץ ל־JSON.
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        json_text = re.search(r"\{.*\}", text, re.DOTALL).group()
        parsed = json.loads(repair_json(json_text))

        base_score = parsed.get("base_score", 0)
        issues = parsed.get("common_issues", [])
        avg_cost = parsed.get("avg_repair_cost_ILS", 0)
        search_flag = parsed.get("search_performed", False)
        summary = parsed.get("reliability_summary", "אין מידע.")
        detailed_costs = parsed.get("issues_with_costs", [])

        # -------------------------------------------------------
        # הצגת תוצאות
        # -------------------------------------------------------
        if search_flag:
            st.success("🌐 בוצע חיפוש אינטרנטי בזמן אמת למידע עדכני בישראל.")
        else:
            st.warning("⚠️ לא בוצע חיפוש אינטרנטי — ייתכן שהמידע חלקי או ישן.")

        st.subheader(f"ציון אמינות כולל: {base_score}/100")
        st.write(summary)

        if issues:
            st.markdown("**🔧 תקלות נפוצות:**")
            for i in issues:
                st.markdown(f"- {i}")

        if detailed_costs:
            st.markdown("**💰 עלויות תיקון ממוצעות:**")
            for item in detailed_costs:
                issue = item.get("issue", "")
                cost = item.get("avg_cost_ILS", "")
                src = item.get("source", "")
                st.markdown(f"- {issue}: כ־{cost} ₪ (מקור: {src})")

        if avg_cost > 0:
            st.info(f"עלות תחזוקה ממוצעת כוללת: כ־{avg_cost:,.0f} ₪")

        # -------------------------------------------------------
        # שמירת נתונים
        # -------------------------------------------------------
        new_entry = {
            "date": today,
            "user_id": user_id,
            "make": selected_make,
            "model": selected_model,
            "year": year,
            "base_score": base_score,
            "avg_cost": avg_cost,
            "issues": "; ".join(issues) if isinstance(issues, list) else str(issues),
            "search_performed": search_flag
        }

        df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
        csv_data = df.to_csv(index=False)
        try:
            repo.update_file(csv_path, "update reliability results", csv_data, contents.sha)
        except Exception:
            repo.create_file(csv_path, "create reliability results", csv_data)

        # -------------------------------------------------------
        # עדכון מילון
        # -------------------------------------------------------
        if selected_make not in israeli_car_market_full_compilation:
            israeli_car_market_full_compilation[selected_make] = [selected_model]
        elif selected_model not in israeli_car_market_full_compilation[selected_make]:
            israeli_car_market_full_compilation[selected_make].append(selected_model)

        dict_file = "car_models_dict.py"
        content = "israeli_car_market_full_compilation = " + json.dumps(
            israeli_car_market_full_compilation, ensure_ascii=False, indent=4
        )
        try:
            existing = repo.get_contents(dict_file)
            repo.update_file(dict_file, "auto-update car models", content, existing.sha)
        except Exception:
            repo.create_file(dict_file, "create car models dict", content)
        st.info("📁 המילון עודכן ב־GitHub בהצלחה.")

    except Exception as e:
        st.error(f"שגיאה בעיבוד הבקשה: {e}")
