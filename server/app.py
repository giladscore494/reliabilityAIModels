from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from . import schemas, auth, rate_limits, cache_lookup, models_logic, sheets_layer

app = FastAPI(title="Car Reliability API")

ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '')
origins = [u.strip() for u in ALLOWED_ORIGINS.split(',') if u.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/health')
async def health():
    return {"status": "ok"}


@app.post('/v1/analyze')
async def analyze(payload: schemas.AnalyzeRequest, authorization: str | None = Header(None)):
    # verify auth (optional)
    user = None
    if authorization:
        token = authorization.split('Bearer')[-1].strip()
        try:
            user = auth.verify_google_id_token(token)
        except Exception:
            user = {"user_id": "anonymous"}
    else:
        user = {"user_id": "anonymous"}

    # rate limit check
    if not rate_limits.within_user_daily_limit(user.get('user_id')):
        raise HTTPException(status_code=429, detail='User daily limit exceeded')
    if not rate_limits.within_daily_global_limit():
        raise HTTPException(status_code=429, detail='Global daily limit exceeded')

    # cache lookup
    cached = cache_lookup.get_cached_from_sheet(payload)
    if cached:
        result = models_logic.apply_mileage_logic(cached['result'], payload.mileage_range)
        # update quotas counters (not implemented)
        return {"source": "cache", "used_fallback": False, "km_warn": False, "result": result}

    # call model
    prompt = models_logic.build_prompt(payload)
    model_resp = models_logic.call_model_with_retry(prompt)
    processed = models_logic.apply_mileage_logic(model_resp, payload.mileage_range)

    # append to sheet
    sheets_layer.append_row_to_sheet(user.get('user_id'), payload, processed)

    return {"source": "model", "used_fallback": False, "km_warn": False, "result": processed}


@app.get('/v1/quota')
async def quota(authorization: str | None = Header(None)):
    user_id = 'anonymous'
    if authorization:
        token = authorization.split('Bearer')[-1].strip()
        try:
            user = auth.verify_google_id_token(token)
            user_id = user.get('user_id')
        except Exception:
            user_id = 'anonymous'
    return rate_limits.get_quota_status(user_id)
