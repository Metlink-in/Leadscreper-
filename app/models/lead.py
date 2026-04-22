from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class Lead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    category: int
    industry: str
    source: str
    source_url: str
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: str
    description: str
    ai_score: Optional[int] = None
    ai_summary: Optional[str] = None
    outreach_angle: Optional[str] = None
    contact_priority: Optional[str] = None
    lead_quality: Optional[str] = None
    platform: Optional[str] = None
    post_url: Optional[str] = None
    followers: Optional[str] = None
    scraped_at: datetime
    keywords_matched: List[str]
