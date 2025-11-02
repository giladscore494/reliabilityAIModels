# -*- coding: utf-8 -*-
"""
Pydantic schemas for request/response validation
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request schema for reliability analysis"""
    make: str
    model: str
    sub_model: Optional[str] = ""
    year: int
    fuel_type: str
    transmission: str
    mileage_range: str
    advanced_mode: bool = False


class ScoreBreakdown(BaseModel):
    """Score breakdown by category"""
    engine_transmission_score: Optional[int] = None
    electrical_score: Optional[int] = None
    suspension_brakes_score: Optional[int] = None
    maintenance_cost_score: Optional[int] = None
    satisfaction_score: Optional[int] = None
    recalls_score: Optional[int] = None


class IssueWithCost(BaseModel):
    """Issue with estimated cost"""
    issue: str
    avg_cost_ILS: Optional[int] = None
    source: Optional[str] = None
    severity: Optional[str] = None


class CompetitorBrief(BaseModel):
    """Competitor brief summary"""
    model: str
    brief_summary: str


class AnalysisResult(BaseModel):
    """Analysis result data"""
    base_score_calculated: int
    score_breakdown: Dict[str, Any]
    common_issues: List[str]
    avg_repair_cost_ILS: Optional[int] = None
    issues_with_costs: List[Dict[str, Any]]
    reliability_summary: str
    sources: List[str]
    recommended_checks: List[str]
    common_competitors_brief: List[Dict[str, Any]]
    last_date: Optional[str] = None
    cached_mileage_range: Optional[str] = None


class QuotaInfo(BaseModel):
    """Quota information"""
    user_left_today: int
    global_left_today: int


class AnalyzeResponse(BaseModel):
    """Response schema for reliability analysis"""
    source: str  # "cache" or "model"
    used_fallback: bool
    km_warn: bool
    mileage_note: Optional[str] = None
    result: AnalysisResult
    quota: QuotaInfo


class HistoryItem(BaseModel):
    """Single history record"""
    date: str
    make: str
    model: str
    sub_model: Optional[str] = None
    year: int
    fuel: str
    transmission: str
    mileage_range: str
    base_score_calculated: Optional[int] = None


class HistoryResponse(BaseModel):
    """Response schema for history"""
    items: List[HistoryItem]
    total: int


class LeadPayload(BaseModel):
    """Lead contact information"""
    name: str
    phone: str
    email: str
    note: Optional[str] = ""


class LeadRequest(BaseModel):
    """Request schema for leads"""
    type: str  # "insurance", "financing", "dealer"
    payload: LeadPayload


class QuotaResponse(BaseModel):
    """Response schema for quota check"""
    user_left_today: int
    global_left_today: int


class RoiRequest(BaseModel):
    """Request schema for ROI calculation (optional)"""
    make: str
    model: str
    year: int
    purchase_price: int
    current_mileage: int
    expected_annual_mileage: int


class RoiResponse(BaseModel):
    """Response schema for ROI calculation (optional)"""
    estimated_value_1y: int
    estimated_value_3y: int
    estimated_value_5y: int
    total_cost_of_ownership_1y: int
    total_cost_of_ownership_3y: int
    total_cost_of_ownership_5y: int
