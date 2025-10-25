# -*- coding: utf-8 -*-
# Car Reliability Analyzer – Israel (v3.4.0)
# Sheets + 45d Cache • No auth/signup • 30-char input limit
# Free-text sub-model + A→B fallback (try sub-model; else model-only)
# ✅ NEW: Mileage range input • Transparent score breakdown • Tabs UI
# ✅ NEW: Cache & Sheets include mileage_range + score_breakdown + base_score_calculated

import json, re, datetime, difflib, traceback
import pandas as pd
import streamlit as st
from json_repair import repair_json
import google.generativeai as genai

# ---------- UI ----------
st.set_page_config(page_title="🚗 Car Reliability Analyzer (Sheets)", page_icon="🔧", layout="centered")
st.title("🚗 Car Reliability Analyzer – בדיקת אמינות רכב בישראל (Sheets)")

# ---------- Secrets ----------
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GOOGLE_SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# ---------- Model ----------
if not GEMINI_API_KEY:
    st.error("חסר GEMINI_API_KEY ב-Secrets.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel("gemini-2.5-flash")

# ---------- Models dictionary ----------
from car_models_dict import israeli_car_market_full_compilation

# ---------- Helpers ----------
MAX_LEN = 30

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = re.sub(r"\(.*?\)", " ", str(s))
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def parse_year_range_from_model_label(model_label: str):
    m = re.search(r"\((\d{4})\s*-\s*(\d{4})", str(model_label))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)

def build_prompt(make, model, sub_model, year, fuel_type, transmission, mileage_range):
    extra = f" תת-דגם/תצורה: {sub_model}" if sub_model else ""
    return f"""
אתה מומחה לאמינות רכבים בישראל עם גישה לחיפוש אינטרנטי.
הניתוח חייב להתייחס ספציפית לטווח הקילומטראז' הנתון.
חובה לבצע חיפוש עדכני בעברית ובאנגלית ממקורות אמינים בלבד.
החזר JSON בלבד:

{{
  "search_performed": true,
  "score_breakdown": {{
    "engine_transmission_score": "מספר (1-10)",
    "electrical_score": "מספר (1-10)",
    "suspension_brakes_score": "מספר (1-10)",
    "maintenance_cost_score": "מספר (1-10)",
    "satisfaction_score": "מספר (1-10)",
    "recalls_score": "מספר (1-10)"
  }},
  "base_score_calculated": "מספר (0-100), מבוסס על המשקלות",
  "common_issues": ["תקלות נפוצות בעברית (רלוונטיות לק\"מ)"],
  "avg_repair_cost_ILS": "מספר ממוצע",
  "issues_with_costs": [
    {{"issue": "שם התקלה", "avg_cost_ILS": "מספר", "source": "מקור", "severity": "נמוך/בינוני/גבוה"}}
  ],
  "reliability_summary": "סיכום בעברית (להתייחס להשפעת הק\"מ)",
  "sources": ["רשימת אתרים"],
  "recommended_checks": ["בדיקות מומלצות ספציפיות לדגם זה במוסך"],
  "common_competitors_brief": [
      {{"model": "שם מתחרה 1", "brief_summary": "סיכום אמינות קצר של המתחרה"}},
      {{"model": "שם מתחרה 2", "brief_summary": "סיכום אמינות קצר של המתחרה"}}
  ]
}}

🧮 משקלות לחישוב base_score_calculated (מתוך 100):
מנוע/גיר (35%), חשמל/אלקטרוניקה (20%), מתלים/בלמים (10%), עלות תחזוקה (15%), שביעות רצון (15%), ריקולים (5%).
(הציון לכל קטגוריה הוא 1-10, תכפיל ב-10 כדי לקבל ציון מתוך 100 לכל קטגוריה לפני השקלול)

רכב: {make} {model}{extra} {int(year)}
טווח קילומטראז': {mileage_range}
סוג דלק: {fuel_type}
תיבת הילוכים: {transmission}
כתוב בעברית בלבד.
""".strip()

def safe_json_parse(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        try:
            fixed = repair_json(s)
            return json.loads(fixed)
        except Exception:
            return None

def check_len_or_stop(*values):
    for v in values:
        if v and len(v) > MAX_LEN:
            st.error("הזנה ארוכה מדי — עד 30 תווים")
            st.stop()

# ---------- Sheets ----------
def connect_sheet():
    if not (GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON):
        st.error("אין חיבור למאגר (Secrets חסרים).")
        st.stop()
    try:
        svc = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        if "\\n" in svc.get("private_key",""):
            svc["private_key"] = svc["private_key"].replace("\\n","\n")
        from google.oauth2.service_account import Credentials
        import gspread
        credentials = Credentials.from_service_account_info(
            svc, scopes=["https://www.googleapis.com/auth/spreadsheets",
                         "https://www.googleapis.com/auth/drive"]
        )
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        ws = sh.sheet1

        # v3.4.0 headers (backward compatible additions)
        headers = [
            "date","user_id","make","model","sub_model","year","fuel","transmission",
            "mileage_range",
            "base_score_calculated","score_breakdown","avg_cost","issues","search_performed",
            "reliability_summary","issues_with_costs","sources",
            "recommended_checks","common_competitors_brief"
        ]
        current = ws.row_values(1)
        if [c.lower() for c in current] != headers:
            ws.update("A1",[headers], value_input_option="USER_ENTERED")
        return ws
    except Exception as e:
        st.error("אין חיבור למאגר (שיתוף/הרשאות/Sheet).")
        st.code(repr(e))
        st.stop()

ws = connect_sheet()

def sheet_to_df() -> pd.DataFrame:
    cols = [
        "date","user_id","make","model","sub_model","year","fuel","transmission",
        "mileage_range",
        "base_score_calculated","score_breakdown","avg_cost","issues","search_performed",
        "reliability_summary","issues_with_costs","sources",
        "recommended_checks","common_competitors_brief"
    ]
    try:
        recs = ws.get_all_records()
    except Exception as e:
        st.error("כשל בקריאת המאגר.")
        st.code(repr(e))
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(recs) if recs else pd.DataFrame(columns=cols)

def append_row_to_sheet(row_dict: dict):
    order = [
        "date","user_id","make","model","sub_model","year","fuel","transmission",
        "mileage_range",
        "base_score_calculated","score_breakdown","avg_cost","issues","search_performed",
        "reliability_summary","issues_with_costs","sources",
        "recommended_checks","common_competitors_brief"
    ]
    row = [row_dict.get(k,"") for k in order]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error("כשל בכתיבה למאגר.")
        st.code(repr(e))

# ---------- Limits ----------
GLOBAL_DAILY_LIMIT = 1000
def within_daily_global_limit(df: pd.DataFrame, limit=GLOBAL_DAILY_LIMIT):
    today = datetime.date.today().isoformat()
    cnt = len(df[df.get("date","").astype(str) == today]) if not df.empty and "date" in df.columns else 0
    return (cnt < limit, cnt)

# ---------- Cache (45d) + sub_model A→B + mileage ----------
def match_hits(recent: pd.DataFrame, year: int, make: str, model: str, sub_model: str|None, mileage_range: str, th: float):
    mk, md, sm = normalize_text(make), normalize_text(model), normalize_text(sub_model or "")
    mr = normalize_text(mileage_range or "")
    use_sub = len(sm) > 0

    cand = recent[
        (recent["year"].astype("Int64") == int(year)) &
        (recent["make"].apply(lambda x: similarity(x, mk) >= th)) &
        (recent["model"].apply(lambda x: similarity(x, md) >= th))
    ]
    if use_sub and "sub_model" in recent.columns:
        cand = cand[cand["sub_model"].apply(lambda x: similarity(x, sm) >= th)]
    # mileage exact-ish match when column exists
    if "mileage_range" in recent.columns and mr:
        cand = cand[cand["mileage_range"].apply(lambda x: similarity(str(x), mr) >= 0.97)]

    if "date" in cand.columns:
        return cand.sort_values("date")
    else:
        return cand

def get_cached_from_sheet(make: str, model: str, sub_model: str, year: int, mileage_range: str, max_days=45):
    df = sheet_to_df()
    if df.empty:
        return None, df, False
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    except Exception:
        pass
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=max_days)
    recent = df[df["date"] >= cutoff] if "date" in df.columns else df

    used_fallback = False
    hits = pd.DataFrame()
    for th in (0.97, 0.93):
        hits = match_hits(recent, year, make, model, sub_model, mileage_range, th)
        if not hits.empty:
            break
    if hits.empty and sub_model:
        used_fallback = True
        for th in (0.97, 0.93):
            hits = match_hits(recent, year, make, model, None, mileage_range, th)
            if not hits.empty:
                break
    if hits.empty:
        return None, df, used_fallback

    # Build a "parsed_data-like" object from cache (supports old rows without breakdown)
    def row_to_parsed(r: dict):
        score_breakdown = safe_json_parse(r.get("score_breakdown")) or {}
        issues_with_costs = safe_json_parse(r.get("issues_with_costs")) or []
        recommended_checks = safe_json_parse(r.get("recommended_checks")) or []
        competitors = safe_json_parse(r.get("common_competitors_brief")) or []
        sources = safe_json_parse(r.get("sources")) or r.get("sources","")

        # Back-compat: base_score_calculated may be empty in old rows; fallback to "base_score"
        base_calc = r.get("base_score_calculated")
        if base_calc in [None, "", "nan"]:
            # legacy field name
            legacy_base = r.get("base_score")
            try:
                base_calc = int(round(float(legacy_base)))
            except Exception:
                base_calc = None

        issues_raw = r.get("issues", [])
        if isinstance(issues_raw, str) and issues_raw:
            if ";" in issues_raw:
                issues_list = [x.strip() for x in issues_raw.split(";") if x.strip()]
            elif "," in issues_raw:
                issues_list = [x.strip() for x in issues_raw.split(",") if x.strip()]
            else:
                issues_list = [issues_raw.strip()]
        elif isinstance(issues_raw, list):
            issues_list = [str(x).strip() for x in issues_raw if str(x).strip()]
        else:
            issues_list = []

        return {
            "score_breakdown": score_breakdown,
            "base_score_calculated": base_calc,
            "common_issues": issues_list,
            "avg_repair_cost_ILS": r.get("avg_cost"),
            "issues_with_costs": issues_with_costs,
            "reliability_summary": r.get("reliability_summary") or "",
            "sources": sources,
            "recommended_checks": recommended_checks,
            "common_competitors_brief": competitors,
            "last_date": str(r.get("date").date()) if isinstance(r.get("date"), pd.Timestamp) else str(r.get("date") or "")
        }

    if len(hits) >= 3:
        # aggregate: average numeric fields where possible; use last row for details
        base_series = pd.to_numeric(hits.get("base_score_calculated"), errors="coerce")
        if base_series.isna().all() and "base_score" in hits.columns:
            base_series = pd.to_numeric(hits.get("base_score"), errors="coerce")
        avg_cost_series  = pd.to_numeric(hits.get("avg_cost"), errors="coerce")
        last_row = hits.iloc[-1].to_dict()
        parsed_last = row_to_parsed(last_row)
        parsed_last["is_aggregate"] = True
        parsed_last["count"] = int(len(hits))
        if not base_series.dropna().empty:
            parsed_last["base_score_calculated"] = int(round(base_series.dropna().mean()))
        if not avg_cost_series.dropna().empty:
            parsed_last["avg_repair_cost_ILS"] = int(round(avg_cost_series.dropna().mean()))
        parsed_last["search_performed"] = "true (history aggregate)"
        return parsed_last, df, used_fallback

    row = hits.iloc[-1].to_dict()
    parsed_row = row_to_parsed(row)
    parsed_row["is_aggregate"] = False
    parsed_row["count"] = int(len(hits))
    return parsed_row, df, used_fallback

# ---------- UI (inputs) ----------
st.markdown("### 🔍 בחירת יצרן, דגם ותת-דגם")

# בחירה מהמילון + קלדה חופשית משולבים
make_list = sorted(israeli_car_market_full_compilation.keys())
make_choice = st.selectbox("בחר יצרן:", ["בחר..."] + make_list, index=0)
make_input  = st.text_input("או הזן יצרן ידנית (עד 30 תווים):", max_chars=MAX_LEN)
selected_make = (make_choice if make_choice != "בחר..." else make_input).strip()

selected_model = ""
year_range = None
if selected_make in israeli_car_market_full_compilation:
    models = israeli_car_market_full_compilation[selected_make]
    model_choice = st.selectbox("בחר דגם:", ["בחר דגם..."] + models, index=0)
    model_input  = st.text_input("או הזן דגם ידנית (עד 30 תווים):", max_chars=MAX_LEN)
    selected_model = (model_choice if model_choice != "בחר דגם..." else model_input).strip()
    if selected_model:
        yr_start, yr_end = parse_year_range_from_model_label(selected_model)
        if yr_start and yr_end:
            year_range = (yr_start, yr_end)
else:
    if selected_make:
        model_input  = st.text_input("שם דגם (עד 30 תווים):", max_chars=MAX_LEN)
        selected_model = model_input.strip()

# תת-דגם/תצורה — חופשי תמיד
sub_model = st.text_input("תת-דגם / תצורה (חופשי, עד 30 תווים):", max_chars=MAX_LEN).strip()

# שנתון
if year_range:
    year = st.number_input(f"שנת ייצור ({year_range[0]}–{year_range[1]}):", min_value=year_range[0], max_value=year_range[1], step=1)
else:
    year = st.number_input("שנת ייצור:", min_value=1960, max_value=2025, step=1)

# ✅ NEW: טווח קילומטראז'
mileage_ranges = ["עד 50,000 ק\"מ", "50,000 - 100,000 ק\"מ", "100,000 - 150,000 ק\"מ", "150,000 - 200,000 ק\"מ", "200,000+ ק\"מ"]
mileage_range = st.selectbox("טווח קילומטראז':", mileage_ranges)

col1, col2 = st.columns(2)
with col1:
    fuel_type = st.selectbox("סוג דלק:", ["בנזין", "דיזל", "היברידי", "חשמלי", "אחר"])
with col2:
    transmission = st.selectbox("תיבת הילוכים:", ["אוטומטית", "ידנית"])

st.markdown("---")

# ---------- Render (transparent UI) ----------
def render_like_model(parsed_data: dict, source_tag: str):
    # parsed_data supports:
    # base_score_calculated, score_breakdown{}, reliability_summary,
    # common_issues[], issues_with_costs[], avg_repair_cost_ILS, recommended_checks[], common_competitors_brief[]
    base_score = int(parsed_data.get("base_score_calculated", 0) or 0)
    summary = parsed_data.get("reliability_summary", "")
    score_breakdown = parsed_data.get("score_breakdown", {}) or {}
    issues_list = parsed_data.get("common_issues", []) or []
    detailed_costs_list = parsed_data.get("issues_with_costs", []) or []
    recommended_checks = parsed_data.get("recommended_checks", []) or []
    competitors = parsed_data.get("common_competitors_brief", []) or []
    avg_cost = parsed_data.get("avg_repair_cost_ILS", None)

    st.metric(label="ציון אמינות משוקלל", value=f"{base_score} / 100")
    if summary:
        st.write(summary)

    tab1, tab2, tab3, tab4 = st.tabs(["פירוט הציון", "תקלות ועלויות", "בדיקות מומלצות", "מתחרים"])

    with tab1:
        st.markdown("#### 📊 פירוט הציון (1-10)")
        if score_breakdown:
            c1, c2, c3 = st.columns(3)
            c1.metric("מנוע וגיר", f"{score_breakdown.get('engine_transmission_score', 'N/A')}/10")
            c2.metric("חשמל ואלקטרוניקה", f"{score_breakdown.get('electrical_score', 'N/A')}/10")
            c3.metric("מתלים ובלמים", f"{score_breakdown.get('suspension_brakes_score', 'N/A')}/10")
            c1.metric("עלות אחזקה", f"{score_breakdown.get('maintenance_cost_score', 'N/A')}/10")
            c2.metric("שביעות רצון", f"{score_breakdown.get('satisfaction_score', 'N/A')}/10")
            c3.metric("ריקולים", f"{score_breakdown.get('recalls_score', 'N/A')}/10")
        else:
            st.info("אין נתוני פירוט ציון זמינים מהמאגר לרכב זה.")

    with tab2:
        if issues_list:
            st.markdown("**🔧 תקלות נפוצות:**")
            for i in issues_list:
                st.markdown(f"- {i}")
        if detailed_costs_list:
            st.markdown("**💰 עלויות תיקון (אינדיקטיבי):**")
            for item in detailed_costs_list:
                if isinstance(item, dict):
                    issue = item.get("issue","")
                    cost  = item.get("avg_cost_ILS", 0)
                    severity = item.get("severity", "")
                    tag = f" (חומרה: {severity})" if severity else ""
                    try:
                        cost_txt = f"{int(float(cost))}"
                    except Exception:
                        cost_txt = str(cost)
                    st.markdown(f"- {issue}: כ-{cost_txt} ₪{tag}")
        if not issues_list and not detailed_costs_list:
            st.info("אין מידע על תקלות/עלויות שמורות למקרה זה.")

    with tab3:
        if recommended_checks:
            st.markdown("**🔬 מה כדאי לבדוק במוסך?**")
            for check in recommended_checks:
                st.markdown(f"- {check}")
        else:
            st.info("אין המלצות בדיקה ספציפיות למודל זה במאגר.")

    with tab4:
        if competitors:
            st.markdown("**🚗 מתחרים נפוצים**")
            for comp in competitors:
                st.markdown(f"**{comp.get('model', '')}:** {comp.get('brief_summary', '')}")
        else:
            st.info("אין נתוני מתחרים שמורים למודל זה.")

    if avg_cost not in [None, "", "nan"]:
        try:
            st.info(f"עלות תחזוקה ממוצעת: כ-{int(float(avg_cost))} ₪")
        except Exception:
            st.info(f"עלות תחזוקה ממוצעת (אינדיקטיבי): {avg_cost}")

    if source_tag:
        st.caption(source_tag)

# ---------- Run ----------
if st.button("בדוק אמינות"):
    if not selected_make or not selected_model:
        st.error("יש להזין שם יצרן ודגם.")
        st.stop()

    # רק הגבלת אורך 30 תווים (אין בדיקות תווים נוספות)
    check_len_or_stop(selected_make, selected_model, sub_model)

    # מגבלת מערכת יומית
    df_all = sheet_to_df()
    ok_global, total_global = within_daily_global_limit(df_all, limit=GLOBAL_DAILY_LIMIT)
    if not ok_global:
        st.error(f"חציתם את מגבלת {GLOBAL_DAILY_LIMIT} הבדיקות היומיות (בוצעו {total_global}). נסו מחר.")
        st.stop()

    # Cache קודם (עם A→B fallback + mileage)
    cached_parsed, _, used_fallback = get_cached_from_sheet(
        selected_make, selected_model, sub_model, int(year), mileage_range, max_days=45
    )
    if cached_parsed:
        tag = "✅ מקור: נתון קיים מהמאגר"
        if used_fallback and sub_model:
            tag += " (נמצאה התאמה לפי דגם בלבד)"
        last_date = cached_parsed.get("last_date","")
        if last_date:
            tag += f" (נבדק: {last_date}). לא בוצעה פנייה למודל."
        else:
            tag += ". לא בוצעה פנייה למודל."
        # הצגה שקופה
        render_like_model(cached_parsed, tag)
        st.stop()

    # אין Cache → קריאה למודל
    prompt = build_prompt(selected_make, selected_model, sub_model, int(year), fuel_type, transmission, mileage_range)
    try:
        with st.spinner("מבצע חיפוש אינטרנטי ומחשב ציון..."):
            resp = llm.generate_content(prompt)
            raw = (getattr(resp, "text", "") or "").strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            parsed = json.loads(m.group()) if m else json.loads(repair_json(raw))
    except Exception as e:
        st.error("שגיאה בעיבוד תשובת המודל.")
        st.code(repr(e))
        st.code(traceback.format_exc())
        st.stop()

    # נרמול פלט (תמיכה אם המודל עדיין החזיר base_score בלבד)
    score_breakdown = parsed.get("score_breakdown", {}) or {}
    base_calc = parsed.get("base_score_calculated")
    if base_calc in [None, "", "nan"]:
        # fallback לשדה ישן אם הופיע
        legacy = parsed.get("base_score", 0)
        try:
            base_calc = int(round(float(legacy)))
        except Exception:
            base_calc = 0

    result_obj = {
        "score_breakdown": score_breakdown,
        "base_score_calculated": int(base_calc or 0),
        "common_issues": parsed.get("common_issues", []) or [],
        "avg_repair_cost_ILS": parsed.get("avg_repair_cost_ILS", 0),
        "issues_with_costs": parsed.get("issues_with_costs", []) or [],
        "reliability_summary": parsed.get("reliability_summary", "אין מידע."),
        "sources": parsed.get("sources", []) or [],
        "recommended_checks": parsed.get("recommended_checks", []) or [],
        "common_competitors_brief": parsed.get("common_competitors_brief", []) or []
    }

    render_like_model(result_obj, "🌐 מקור: חיפוש בזמן אמת (Gemini)")

    # כתיבה למאגר
    try:
        issues_str = "; ".join(result_obj["common_issues"]) if isinstance(result_obj["common_issues"], list) else str(result_obj["common_issues"])
        issues_with_costs_str = json.dumps(result_obj["issues_with_costs"], ensure_ascii=False)
        sources_str = json.dumps(result_obj["sources"], ensure_ascii=False) if isinstance(result_obj["sources"], list) else str(result_obj["sources"])
        score_breakdown_str = json.dumps(result_obj["score_breakdown"], ensure_ascii=False) if isinstance(result_obj["score_breakdown"], dict) else str(result_obj["score_breakdown"])
        recommended_checks_str = json.dumps(result_obj["recommended_checks"], ensure_ascii=False)
        competitors_str = json.dumps(result_obj["common_competitors_brief"], ensure_ascii=False)
    except Exception:
        issues_str = str(result_obj["common_issues"])
        issues_with_costs_str = str(result_obj["issues_with_costs"])
        sources_str = str(result_obj["sources"])
        score_breakdown_str = str(result_obj["score_breakdown"])
        recommended_checks_str = str(result_obj["recommended_checks"])
        competitors_str = str(result_obj["common_competitors_brief"])

    append_row_to_sheet({
        "date": datetime.date.today().isoformat(),
        "user_id": "anonymous",
        "make": normalize_text(selected_make),
        "model": normalize_text(selected_model),
        "sub_model": normalize_text(sub_model),
        "year": int(year),
        "fuel": fuel_type,
        "transmission": transmission,
        "mileage_range": mileage_range,
        "base_score_calculated": int(result_obj["base_score_calculated"] or 0),
        "score_breakdown": score_breakdown_str,
        "avg_cost": result_obj["avg_repair_cost_ILS"],
        "issues": issues_str,
        "search_performed": "true",
        "reliability_summary": result_obj["reliability_summary"],
        "issues_with_costs": issues_with_costs_str,
        "sources": sources_str,
        "recommended_checks": recommended_checks_str,
        "common_competitors_brief": competitors_str
    })

st.markdown("---")
st.caption("כל המידע מוצג כשירות עזר בלבד — אין לראות בתוצאה המלצה מקצועית.")
