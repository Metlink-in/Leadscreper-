from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import FileResponse

from app.config import settings
from app.services.export_service import generate_csv, generate_json, generate_pdf
from app.services.db_service import db_service
from app.models.lead import Lead
from app.services.dependencies import require_user

router = APIRouter()

@router.get("/api/export/{format}")
async def export_leads(
    request: Request,
    format: Literal["csv", "json", "pdf"],
    search_id: str = Query(...),
    user = Depends(require_user)
) -> FileResponse:
    search_data = await db_service.get_search(search_id, user_id=str(user["_id"]))
    if not search_data:
        raise HTTPException(status_code=404, detail="Search ID not found")
        
    leads = [Lead(**lead) if isinstance(lead, dict) else lead for lead in search_data["leads"]]

    filename = f"lead-export-{search_id}.{format}"
    if format == "csv":
        path = generate_csv(leads, settings.export_dir, filename)
        media_type = "text/csv"
    elif format == "json":
        path = generate_json(leads, settings.export_dir, filename)
        media_type = "application/json"
    else:
        path = generate_pdf(leads, settings.export_dir, filename)
        media_type = "application/pdf"
        
    if not Path(path).exists():
        raise HTTPException(status_code=500, detail="Failed to generate export file")
    return FileResponse(path, filename=Path(path).name, media_type=media_type)
