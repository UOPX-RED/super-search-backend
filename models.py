# models.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class TextPayload(BaseModel):
    source_id: str
    content_type: str = Field(..., description="Type of content (e.g., course, program, assignment)")
    text: str
    keywords: List[str] = Field(default_factory=list, description="Keywords or phrases to search for")
    metadata: Optional[Dict[str, Any]] = {}


class HighlightedSection(BaseModel):
    start_index: int
    end_index: int
    matched_text: str
    reason: str
    confidence: float


class AnalysisResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str  # New field for tracking requests
    source_id: str
    content_type: str
    original_text: str
    keywords_searched: List[str] = []
    highlighted_sections: List[HighlightedSection] = []
    has_flags: bool = False
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    keywords_matched: List[str] = []
