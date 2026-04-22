from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: List[int] = Field(..., min_items=1)
    industries: List[str] = Field(..., min_items=1)
    country: Optional[str] = None
    city: Optional[str] = None
    keywords: Optional[List[str]] = None
    max_results: Optional[int] = 50
    enable_ai: Optional[bool] = True
