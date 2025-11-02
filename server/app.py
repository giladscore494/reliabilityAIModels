# -*- coding: utf-8 -*-
"""
FastAPI main application
Car Reliability Analyzer API Server
"""
import datetime
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import pandas as pd

from settings import ALLOWED_ORIGINS, REQUIRED_HEADERS
from schemas import (
    AnalyzeRequest, AnalyzeResponse, AnalysisResult, QuotaInfo,
    HistoryResponse, HistoryItem, LeadRequest, QuotaResponse,
    RoiRequest, RoiResponse
)
from auth import get_user_id_from_header
from rate_limits import check_rate_limits, get_remaining_quota
from cache_lookup import get_cached_from_sheet
from models_logic import build_prompt, call_model_with_retry, apply_mileage_logic
from sheets_layer import sheet_to_df, append_row_to_sheet
from leads import save_lead
from roi import calculate_roi


# Create FastAPI app
app = FastAPI(
    title="Car Reliability Analyzer API",
    description="API for car reliability analysis in Israel",
    version="4.0.0"
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}


@app.get("/v1/quota")
async def get_quota(authorization: Optional[str] = Header(None)):
    """Get current quota status"""
    user_id = get_user_id_from_header(authorization)
    user_left, global_left = get_remaining_quota(user_id)
    
    return QuotaResponse(
        user_left_today=user_left,
        global_left_today=global_left
    )


@app.post("/v1/analyze")
async def analyze_reliability(
    request: AnalyzeRequest,
    authorization: Optional[str] = Header(None)
) -> AnalyzeResponse:
    """Analyze car reliability"""
    
    # Get user ID
    user_id = get_user_id_from_header(authorization)
    
    # Check rate limits
    can_proceed, user_cnt, global_cnt = check_rate_limits(user_id)
    
    if not can_proceed:
        if global_cnt >= 1000:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Global daily limit reached. Please try again tomorrow."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="User daily limit reached. Please try again tomorrow."
            )
    
    # Try cache first
    cached = None
    used_fallback = False
    mileage_matched = False
    km_warn = False
    mileage_note = None
    
    try:
        cached, _, used_fallback, mileage_matched = get_cached_from_sheet(
            request.make,
            request.model,
            request.sub_model,
            request.year,
            request.mileage_range
        )
    except Exception:
        cached = None
    
    if cached:
        # Apply mileage logic to cached result
        cached, mileage_note = apply_mileage_logic(cached, request.mileage_range)
        km_warn = not mileage_matched
        
        # Get remaining quota
        user_left, global_left = get_remaining_quota(user_id)
        
        return AnalyzeResponse(
            source="cache",
            used_fallback=used_fallback,
            km_warn=km_warn,
            mileage_note=mileage_note,
            result=AnalysisResult(**cached),
            quota=QuotaInfo(
                user_left_today=max(0, user_left),
                global_left_today=max(0, global_left)
            )
        )
    
    # Call AI model
    try:
        prompt = build_prompt(
            request.make,
            request.model,
            request.sub_model,
            request.year,
            request.fuel_type,
            request.transmission,
            request.mileage_range
        )
        result = call_model_with_retry(prompt)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI model failed: {repr(e)}"
        )
    
    # Apply mileage adjustment
    result, mileage_note = apply_mileage_logic(result, request.mileage_range)
    
    # Save to sheet
    try:
        row = {
            "date": datetime.date.today().isoformat(),
            "user_id": user_id,
            "make": request.make,
            "model": request.model,
            "sub_model": request.sub_model or "",
            "year": request.year,
            "fuel": request.fuel_type,
            "transmission": request.transmission,
            "mileage_range": request.mileage_range,
            "base_score_calculated": result.get("base_score_calculated", ""),
            "score_breakdown": json.dumps(result.get("score_breakdown", {}), ensure_ascii=False),
            "avg_cost": result.get("avg_repair_cost_ILS", ""),
            "issues": "; ".join(result.get("common_issues", []) or []),
            "search_performed": bool(result.get("search_performed", True)),
            "reliability_summary": result.get("reliability_summary", ""),
            "issues_with_costs": json.dumps(result.get("issues_with_costs", []), ensure_ascii=False),
            "sources": json.dumps(result.get("sources", []), ensure_ascii=False),
            "recommended_checks": json.dumps(result.get("recommended_checks", []), ensure_ascii=False),
            "common_competitors_brief": json.dumps(result.get("common_competitors_brief", []), ensure_ascii=False),
        }
        append_row_to_sheet(row)
    except Exception as e:
        # Don't fail the request if saving fails
        pass
    
    # Get remaining quota after this request
    user_left, global_left = get_remaining_quota(user_id)
    
    # Prepare response
    result["last_date"] = datetime.date.today().isoformat()
    result["cached_mileage_range"] = request.mileage_range
    
    return AnalyzeResponse(
        source="model",
        used_fallback=False,
        km_warn=False,
        mileage_note=mileage_note,
        result=AnalysisResult(**result),
        quota=QuotaInfo(
            user_left_today=max(0, user_left - 1),
            global_left_today=max(0, global_left - 1)
        )
    )


@app.get("/v1/history")
async def get_history(
    limit: int = 100,
    offset: int = 0,
    authorization: Optional[str] = Header(None)
) -> HistoryResponse:
    """Get analysis history for the user"""
    
    user_id = get_user_id_from_header(authorization)
    
    if user_id == "anonymous":
        # Return empty history for anonymous users
        return HistoryResponse(items=[], total=0)
    
    try:
        df = sheet_to_df()
        
        if df.empty:
            return HistoryResponse(items=[], total=0)
        
        # Filter by user_id
        user_df = df[df["user_id"].astype(str) == user_id]
        
        if user_df.empty:
            return HistoryResponse(items=[], total=0)
        
        # Sort by date descending
        if "date" in user_df.columns:
            try:
                user_df["date"] = pd.to_datetime(user_df["date"], errors="coerce")
                user_df = user_df.sort_values("date", ascending=False)
            except Exception:
                pass
        
        total = len(user_df)
        
        # Apply pagination
        paginated = user_df.iloc[offset:offset + limit]
        
        # Convert to list of HistoryItem
        items = []
        for _, row in paginated.iterrows():
            try:
                date_str = row.get("date")
                if isinstance(date_str, pd.Timestamp):
                    date_str = str(date_str.date())
                elif date_str:
                    date_str = str(date_str)[:10]
                else:
                    date_str = ""
                
                item = HistoryItem(
                    date=date_str,
                    make=str(row.get("make", "")),
                    model=str(row.get("model", "")),
                    sub_model=str(row.get("sub_model", "")) if row.get("sub_model") else None,
                    year=int(row.get("year", 0)),
                    fuel=str(row.get("fuel", "")),
                    transmission=str(row.get("transmission", "")),
                    mileage_range=str(row.get("mileage_range", "")),
                    base_score_calculated=int(row.get("base_score_calculated", 0)) if row.get("base_score_calculated") else None
                )
                items.append(item)
            except Exception:
                continue
        
        return HistoryResponse(items=items, total=total)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {repr(e)}"
        )


@app.get("/v1/history/export.csv")
async def export_history_csv(authorization: Optional[str] = Header(None)):
    """Export user history as CSV"""
    
    user_id = get_user_id_from_header(authorization)
    
    if user_id == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to export history"
        )
    
    try:
        df = sheet_to_df()
        
        if df.empty:
            # Return empty CSV
            csv_data = pd.DataFrame(columns=REQUIRED_HEADERS).to_csv(index=False)
        else:
            # Filter by user_id
            user_df = df[df["user_id"].astype(str) == user_id]
            csv_data = user_df.to_csv(index=False)
        
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=history_{user_id}_{datetime.date.today().isoformat()}.csv"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export history: {repr(e)}"
        )


@app.post("/v1/leads")
async def create_lead(
    lead: LeadRequest,
    authorization: Optional[str] = Header(None)
):
    """Submit a lead"""
    
    user_id = get_user_id_from_header(authorization)
    
    try:
        success = save_lead(lead, user_id)
        
        if success:
            return {"status": "success", "message": "Lead saved successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save lead"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save lead: {repr(e)}"
        )


@app.post("/v1/roi")
async def calculate_roi_endpoint(request: RoiRequest) -> RoiResponse:
    """Calculate ROI and future value estimates (optional)"""
    try:
        return calculate_roi(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate ROI: {repr(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
