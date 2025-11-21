
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class RevisionCreate(BaseModel):
    source_id: str
    raw_content: str
    extracted_data: Optional[Dict[str, Any]] = None
    status: str = "processed"

class RevisionResponse(BaseModel):
    revision_id: str
    source_id: str
    scraped_at: datetime
    status: str
    ai_summary: Optional[str]
    was_change_detected: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChangeDiffResponse(BaseModel):
    diff_id: str
    new_revision_id: str
    old_revision_id: str
    diff_patch: Optional[Dict[str, Any]]
    ai_confidence: Optional[float]
    
    class Config:
        from_attributes = True

class RevisionWithDiffResponse(BaseModel):
    revision: RevisionResponse
    change_diff: Optional[ChangeDiffResponse]