# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v1.5.0
# בדיקת אמינות רכב לפי יצרן, דגם ושנתון
# כולל מילון דינמי, חיפוש אינטרנטי, Cache, והגבלת בקשות יומית
# ===========================================================

import os, json, re, datetime
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
# טעינת מילון יצרנים ודגמים
# -----------------------------------------------------------
from car_models_dict import israeli_car_market_full_compilation

# -----------------------------------------------------------
# GitHub הגדרות
# -----------------------------------------------------------
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)
csv_path = "reliability_results.csv"

# -----------------------------------------------------------
# פונקציה לבדוק cache של חיפושים קודמים (45 יום)
# -----------------------------------------------------------
def get_cached(make, model, year):
    try:
        contents = repo.get_contents(csv_path)
        df = pd.read_csv(contents.download_url)

        for col in ["make", "model"]:
            df[col] = df[col].astype(str).fillna("").str.strip()
        df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(int)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=45)
        recent_df = df[df["date"] >= cutoff_date]

        match = recent_df[
            (recent_df["make"].str.lower() == make.lower()) &
            (recent_df["model"].str.lower() == model.lower()) &
            (recent_df["year"] == int(year))
        ]

        if not match.empty:
            return match.iloc[-1].to_dict()
        return None
    except Exception:
        return None

# -----------------------------------------------------------
# פונקציה לשמירה ל־GitHub (CSV)
# -----------------------------------------------------------
def append_to_github_csv(user_id, make, model_name, year, base_score, avg_cost, issues, search_performed):
    try:
        try:
            contents = repo.get_contents(csv_path)
            df = pd.read_csv(contents.download_url)
        except Exception:
            df = pd.DataFrame()

        required_cols = ["date", "user_id", "make", "model", "year", "base_score", "avg_cost", "issues", "search_performed"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""
        df = df[required_cols]

        new_entry = {
            "date": datetime.date.today().isoformat(),
            "user_id": user_id,
            "make": make,
            "model": model_name,
            "year": year,
            "base_score": base_score,
            "avg_cost": avg_cost,
            "issues": "; ".join(issues) if isinstance(issues, list) else str(issues),
            "search_performed": search_performed
        }

        df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
        csv_data = df.to_csv(index=False)

        try:
            repo.update_file(csv_path, "update reliability results", csv_data, contents.sha)
        except Exception:
            repo.create_file(csv_path, "create reliability results", csv_data)

    except Exception as e:
        st.warning(f"⚠️ לא ניתן לשמור ל־GitHub: {e}")

# -----------------------------------------------------------
# פונקציית בדיקת מגבלת בקשות יומית
# -----------------------------------------------------------
def check_daily_limit():
    try:
        contents = repo.get_contents(csv_path)
        df = pd.read_csv(contents.download_url)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        today = pd.Timestamp.now().date()
        today_df = df[df["date"].dt.date == today]
        total_today = len(today_df)

        if total_today >= 1000:
            return False, total_today
        return True, total_today
    except Exception:
        return True, 0  # אם אין קובץ עדיין – לא לחסום

# -----------------------------------------------------------
# ממשק בחירת יצרן/דגם – כולל הקלדה חופשית
# -----------------------------------------------------------
make_list = sorted(israeli_car_market_full_compilation.keys())
st.markdown("### 🔍 בחר יצרן ודגם לבדיקה")

make_input = st.text_input("הקלד יצרן (או בחר מהרשימה):")
make_choice = st.selectbox("או בחר יצרן מהרשימה:", ["בחר..."] + make_list)
selected_make = make_input.strip() if make_input else (make_choice if make_choice != "בחר..." else "")
selected_model = ""

if selected_make in israeli_car_market_full_compilation:
    models = israeli_car_market_full_compilation[selected_make]
    model_input = st.text_input(f"או הקלד דגם של {selected_make}:")
    model_choice = st.selectbox(f"או בחר דגם של {selected_make}:", ["בחר דגם..."] + models)
    selected_model = model_input.strip() if model_input else (model_choice if model_choice != "בחר דגם..." else "")
else:
    st.warning("שם החברה לא מופיע במערכת. יש להזין ידנית:")
    selected_make = st.text_input("שם חברה:")
    selected_model = st.text_input("שם דגם:")

year = st.number_input("שנת ייצור:", min_value=2000, max_value=2025, step=1)

# -----------------------------------------------------------
# הפעלת בדיקה
# -----------------------------------------------------------
if st.button("בדוק אמינות"):
    if not selected_make or not selected_model:
        st.error("יש להזין שם חברה ודגם תקינים.")
        st.stop()

    # בדיקת מגבלת שימוש
    ok, total_today = check_daily_limit()
    if not ok:
        st.error(f"❌ חצית את מגבלת 1000 הבדיקות היומיות (כבר בוצעו {total_today}). נסה שוב מחר.")
        st.stop()
    else:
        st.info(f"ניצלו {total_today}/1000 בקשות להיום.")

    user_id = st.session_state.get("user_id", "anonymous")
    st.info(f"מתבצעת בדיקת אמינות עבור {selected_make} {selected_model} ({year})...")

    cached_row = get_cached(selected_make, selected_model, year)
    if cached_row:
        st.success("✅ נמצאה תוצאה שמורה מ־45 הימים האחרונים.")
        st.subheader(f"ציון אמינות כולל: {cached_row['base_score']}/100")
        st.info(f"עלות תחזוקה ממוצעת: כ־{cached_row['avg_cost']} ₪")
        st.write(f"תקלות נפוצות: {cached_row['issues']}")
        st.write(f"נמצא באמצעות חיפוש אינטרנטי: {cached_row['search_performed']}")
        st.stop()

    prompt = f"""
    אתה מומחה לאמינות רכבים בישראל עם גישה לחיפוש אינטרנטי.
    חובה לבצע חיפוש עדכני בעברית ובאנגלית ממקורות אמינים בלבד.
    החזר JSON בלבד עם הנתונים הבאים:
   **You must perform an internet search for information sources for the parameters I requested.**

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
    כתוב בעברית בלבד.
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        json_text = re.search(r"\{.*\}", text, re.DOTALL).group()
        parsed = json.loads(json_text)

        base_score = parsed.get("base_score", 0)
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
            st.markdown("**💰 עלויות תיקון:**")
            for item in detailed_costs:
                st.markdown(f"- {item.get('issue', '')}: כ־{item.get('avg_cost_ILS', 0)} ₪ (מקור: {item.get('source', '')})")

        append_to_github_csv(user_id, selected_make, selected_model, year, base_score, avg_cost, issues, search_flag)

        if selected_make not in israeli_car_market_full_compilation:
            israeli_car_market_full_compilation[selected_make] = [selected_model]
        elif selected_model not in israeli_car_market_full_compilation[selected_make]:
            israeli_car_market_full_compilation[selected_make].append(selected_model)

        dict_file = "car_models_dict.py"
        content = "israeli_car_market_full_compilation = " + json.dumps(israeli_car_market_full_compilation, ensure_ascii=False, indent=4)
        try:
            existing = repo.get_contents(dict_file)
            repo.update_file(dict_file, "auto-update car models", content, existing.sha)
        except Exception:
            repo.create_file(dict_file, "create car models dict", content)

        st.info("📁 המילון עודכן בהצלחה ב־GitHub.")

    except Exception as e:
        st.error(f"שגיאה בעיבוד הבקשה: {e}")
