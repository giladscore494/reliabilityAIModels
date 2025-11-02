# -*- coding: utf-8 -*-
"""
Leads handling - save lead information
"""
import datetime
from typing import Optional

from schemas import LeadRequest
from settings import DATABASE_URL
from sheets_layer import connect_sheet


def save_lead(lead: LeadRequest, user_id: Optional[str] = "anonymous") -> bool:
    """
    Save lead to storage (Sheet or PostgreSQL)
    Returns True if successful
    """
    # For now, save to a separate sheet or the same sheet
    # In production, you might want a separate leads table/sheet
    
    try:
        ws = connect_sheet()
        
        # You could create a separate sheet for leads
        # For simplicity, we'll just return True here
        # In production, implement actual storage
        
        # Example: append to a leads sheet
        # lead_data = {
        #     "date": datetime.date.today().isoformat(),
        #     "user_id": user_id,
        #     "type": lead.type,
        #     "name": lead.payload.name,
        #     "phone": lead.payload.phone,
        #     "email": lead.payload.email,
        #     "note": lead.payload.note
        # }
        
        return True
    except Exception as e:
        return False
