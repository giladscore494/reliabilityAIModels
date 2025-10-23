# -*- coding: utf-8 -*-
# ===========================================================
# 🇮🇱 Car Reliability Analyzer v1.2
# חישוב אמינות רכב לפי יצרן, דגם ושנתון עם חיפוש אינטרנטי בעברית
# ===========================================================

import os, json, re, time, datetime
import pandas as pd
import streamlit as st
from github import Github
from json_repair import repair_json

# -----------------------------------------------------------
# טעינת מילון דגמים
# -----------------------------------------------------------
from car_models_dict import israeli_car_market_full_compilation

# -----------------------------------------------------------
# הגדרות בסיסיות
# -----------------------------------------------------------
st.set_page_config(page_title="🔧 Car Reliability Analyzer", page_icon="🚗", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב")

# -----------------------------------------------------------
# טעינת מפתחות מסודות (Streamlit Secrets)
# -----------------------------------------------------------
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
GITHUB_REPO = st.secrets.get("GITHUB_REPO")

if not GEMINI_API_KEY or not GITHUB_TOKEN or not GITHUB_REPO:
    st.error("⚠️ חסרים מפתחות במשתני הסוד (Secrets) של Streamlit. ודא שהזנת GEMINI_API_KEY, GITHUB_TOKEN ו־GITHUB_REPO.")
    st.stop()

# -----------------------------------------------------------
# הגדרת מודל Gemini
# -----------------------------------------------------------
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# -----------------------------------------------------------
# פונקציה לשמירה ל־GitHub
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
            df = pd.DataFrame(columns=["date", "make", "model", "year", "base_score", "avg_cost", "issues", "search_performed"])

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

        # שמירה חזרה לגיטהאב
        csv_data = df.to_csv(index=False)
        if 'contents' in locals():
            repo.update_file(contents.path, "update reliability results", csv_data, contents.sha)
        else:
            repo.create_file(file_path, "create reliability results", csv_data)
        st.success("✅ הנתונים נשמרו בהצלחה ל־GitHub.")
    except Exception as e:
        st.warning(f"⚠️ לא ניתן לשמור ל־GitHub: {e}")

# -----------------------------------------------------------
# ממשק משתמש
# -----------------------------------------------------------
make = st.selectbox("בחר יצרן:", sorted(israeli_car_market_full_compilation.keys()))
model_input = st.text_input("הכנס דגם (לדוגמה: Corolla, Sportage, i30):")
year = st.number_input("שנת ייצור:", min_value=2000, max_value=2025, step=1)

if st.button("בדוק אמינות"):
    if not model_input:
        st.warning("הכנס שם דגם קודם.")
        st.stop()

    # בדיקה אם הדגם קיים במילון
    known_models = [m.lower() for m in israeli_car_market_full_compilation.get(make, [])]
    is_known = model_input.lower() in known_models

    # -----------------------------------------------------------
    # פרומפט חכם לחיפוש אינטרנטי
    # -----------------------------------------------------------
    if not is_known:
        st.info("🔍 לא נמצא במילון — נשלחת בקשה ל-Gemini עם חיפוש אינטרנטי בעברית ובאנגלית...")

        prompt = f"""
        אתה פועל כחוקר אמינות רכבים בישראל, עם גישה מלאה לחיפוש אינטרנטי.
        חובה עליך לבצע חיפוש בזמן אמת בעברית ובאנגלית ממקורות עדכניים ואמינים בלבד.
        יש לציין האם בוצע בפועל חיפוש אינטרנטי ולהחזיר דיווח מפורש על כך.

        בדוק את הדגם:
        יצרן: {make}
        דגם: {model_input}
        שנת ייצור: {year}

        🔎 מקורות מומלצים:
        - CarsForum.co.il
        - iCar.co.il
        - Edmunds / J.D. Power / Carwow
        - Consumer Reports
        - סקירות משתמשים באתרים מקומיים

        ✳️ החזר JSON תקני בלבד במבנה הבא:
        {{
            "search_performed": true או false,        
            "base_score": מספר בין 0 ל-100,          
            "common_issues": [תקלות נפוצות בעברית],
            "avg_repair_cost_ILS": מספר ממוצע,        
            "issues_with_costs": [
                {{
                    "issue": "שם התקלה בעברית",
                    "avg_cost_ILS": מספר מוערך,
                    "source": "מקור"
                }}
            ],
            "reliability_summary": "סיכום בעברית על רמת האמינות",
            "sources": ["רשימת אתרים שבהם השתמשת"]
        }}

        🧮 משקלות חישוב לציון אמינות (base_score):
        - תקלות מכניות חמורות (מנוע, גיר, מערכת היברידית): 35%
        - תקלות חשמל ואלקטרוניקה: 20%
        - בלאי מתלים, בלמים וצמיגים: 10%
        - עלות תחזוקה וחלקים בישראל: 15%
        - שביעות רצון בעלי רכב (ביקורות): 15%
        - ריקולים ודוחות בטיחות: 5%

        🔔 הנחיות קריטיות:
        - חובה לציין במפורש אם הופעל חיפוש באינטרנט.
        - חובה להחזיר עלויות תיקון ריאליות (₪) לפי מחירי שוק בישראל.
        - השתמש במידע עדכני בלבד (2023–2025).
        - אל תמציא מידע. אם אין מקור, כתוב "אין מידע זמין".
        - כתוב את כל התיאורים בעברית בלבד.
        - הצג JSON תקין בלבד, ללא טקסט חופשי נוסף.
        """

        try:
            response = model.generate_content(prompt)
            text = response.text.strip()

            # ניקוי JSON והצגת פלט
            json_text = re.search(r"\{.*\}", text, re.DOTALL).group()
            parsed = json.loads(json_text)
            base_score = parsed.get("base_score", 0)
            issues = parsed.get("common_issues", [])
            avg_cost = parsed.get("avg_repair_cost_ILS", 0)
            search_flag = parsed.get("search_performed", False)
            issues_detailed = parsed.get("issues_with_costs", [])
            summary = parsed.get("reliability_summary", "אין סיכום זמין.")

            if search_flag:
                st.success("🌐 בוצע חיפוש אינטרנטי למידע עדכני על תקלות ועלויות בישראל.")
            else:
                st.warning("⚠️ לא בוצע חיפוש אינטרנטי — ייתכן שהמידע אינו עדכני.")

            st.subheader(f"ציון אמינות כולל: {base_score}/100")
            st.write(summary)

            if issues:
                st.markdown("**🔧 תקלות נפוצות:**")
                for i in issues:
                    st.markdown(f"- {i}")

            if issues_detailed:
                st.markdown("**💰 פירוט עלויות תיקון ממוצעות (₪):**")
                for i in issues_detailed:
                    issue = i.get("issue", "")
                    cost = i.get("avg_cost_ILS", "")
                    src = i.get("source", "")
                    st.markdown(f"- {issue}: כ־{cost} ₪ (מקור: {src})")

            if avg_cost > 0:
                st.info(f"💵 עלות תחזוקה ממוצעת כוללת: כ־{avg_cost:,.0f} ₪")

            append_to_github_csv(make, model_input, year, base_score, avg_cost, issues, search_flag)

        except Exception as e:
            st.error(f"שגיאה בעיבוד: {e}")
            st.stop()

    else:
        st.success(f"✅ {make} {model_input} נמצא במילון – אין צורך בשליפת אינטרנט.")
        st.info("זהו דגם נפוץ בישראל. ניתן להריץ בדיקות אמינות רק עבור דגמים שאינם במילון.")
