from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.config import settings
from app.services.export_service import generate_csv, generate_json, generate_pdf
from app.services.db_service import db_service
from app.models.lead import Lead

router = APIRouter()


@router.get("/api/export/{format}")
async def export_leads(
    request: Request,
    format: Literal["csv", "json", "pdf"],
    search_id: str = Query(...),
) -> FileResponse:
    store = request.app.state.search_store
    
    if search_id in store:
        leads = store[search_id]["leads"]
    else:
        search_data = await db_service.get_search(search_id)
        if not search_data:
            raise HTTPException(status_code=404, detail="Search ID not found")
        # Ensure we convert DB dictionaries back to Lead objects for generate_pdf/etc if necessary
        # wait, generate_csv expects Lead objects.
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
