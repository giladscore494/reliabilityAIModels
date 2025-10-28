# -*- coding: utf-8 -*-
"""
ROI and future value calculations (optional module)
"""
from schemas import RoiRequest, RoiResponse


def calculate_roi(request: RoiRequest) -> RoiResponse:
    """
    Calculate ROI and future value estimates
    This is a simplified implementation - can be enhanced with real data
    """
    # Simple depreciation model
    # Assume 15% depreciation per year for first 3 years, then 10%
    
    current_value = request.purchase_price
    
    # Year 1
    depreciation_1y = 0.15
    value_1y = int(current_value * (1 - depreciation_1y))
    
    # Year 3
    depreciation_3y = 0.15 + 0.15 + 0.10
    value_3y = int(current_value * (1 - depreciation_3y))
    
    # Year 5
    depreciation_5y = 0.15 + 0.15 + 0.10 + 0.10 + 0.10
    value_5y = int(current_value * (1 - depreciation_5y))
    
    # Estimated annual maintenance costs (simplified)
    annual_maintenance = 5000  # Base cost
    
    # TCO = depreciation + maintenance
    tco_1y = (current_value - value_1y) + annual_maintenance
    tco_3y = (current_value - value_3y) + (annual_maintenance * 3)
    tco_5y = (current_value - value_5y) + (annual_maintenance * 5)
    
    return RoiResponse(
        estimated_value_1y=value_1y,
        estimated_value_3y=value_3y,
        estimated_value_5y=value_5y,
        total_cost_of_ownership_1y=tco_1y,
        total_cost_of_ownership_3y=tco_3y,
        total_cost_of_ownership_5y=tco_5y
    )
