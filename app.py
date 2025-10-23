# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v1.3
# בדיקת אמינות רכב לפי יצרן, דגם ושנתון עם חיפוש אינטרנטי
# כולל עדכון מילון אוטומטי ושמירה ל-GitHub
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
# פונקציה לשמירה ל-GitHub (CSV)
# -----------------------------------------------------------
def append_to_github_csv(make, model_name, year, base_score, avg_cost, issues, search_performed):
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        file_path = "reliability_results.csv"

        try:
            contents = repo.get_contents(file_path)
            df = pd.read_csv(contents.download_url)
        except Exception:
            df = pd.DataFrame(columns=[
                "date", "make", "model", "year", "base_score",
                "avg_cost", "issues", "search_performed"
            ])

        new_entry = {
            "date": datetime.date.today().isoformat(),
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
            repo.update_file(file_path, "update reliability results", csv_data, contents.sha)
        except Exception:
            repo.create_file(file_path, "create reliability results", csv_data)

        st.success("✅ הנתונים נשמרו ל־GitHub בהצלחה.")
    except Exception as e:
        st.warning(f"⚠️ לא ניתן לשמור ל־GitHub: {e}")

# -----------------------------------------------------------
# ממשק משתמש חכם – בחירת יצרן ודגם
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
# הפעלת בדיקה
# -----------------------------------------------------------
if st.button("בדוק אמינות"):
    if not selected_make or not selected_model:
        st.error("יש להזין שם חברה ודגם תקינים.")
        st.stop()

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
        parsed = json.loads(json_text)

        base_score = parsed.get("base_score", 0)
        issues = parsed.get("common_issues", [])
        avg_cost = parsed.get("avg_repair_cost_ILS", 0)
        search_flag = parsed.get("search_performed", False)
        summary = parsed.get("reliability_summary", "אין מידע.")
        detailed_costs = parsed.get("issues_with_costs", [])

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

        # עדכון מילון אם מדובר בחברה/דגם חדשים
        if selected_make not in israeli_car_market_full_compilation:
            israeli_car_market_full_compilation[selected_make] = [selected_model]
        elif selected_model not in israeli_car_market_full_compilation[selected_make]:
            israeli_car_market_full_compilation[selected_make].append(selected_model)

        # שמירת תוצאות החיפוש
        append_to_github_csv(selected_make, selected_model, year, base_score, avg_cost, issues, search_flag)

        # שמירת מילון מעודכן
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(GITHUB_REPO)
            dict_file = "car_models_dict.py"
            content = "israeli_car_market_full_compilation = " + json.dumps(
                israeli_car_market_full_compilation, ensure_ascii=False, indent=4
            )
            try:
                existing = repo.get_contents(dict_file)
                repo.update_file(dict_file, "auto-update car models", content, existing.sha)
            except Exception:
                repo.create_file(dict_file, "create car models dict", content)
            st.info("📁 המילון עודכן אוטומטית ב־GitHub.")
        except Exception as e:
            st.warning(f"⚠️ עדכון המילון נכשל: {e}")

    except Exception as e:
        st.error(f"שגיאה בעיבוד הבקשה: {e}")
