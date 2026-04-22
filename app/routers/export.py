from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.config import settings
from app.services.export_service import generate_csv, generate_json, generate_pdf

router = APIRouter()


@router.get("/api/export/{format}")
async def export_leads(
    request: Request,
    format: Literal["csv", "json", "pdf"],
    search_id: str = Query(...),
) -> FileResponse:
    store = request.app.state.search_store
    if search_id not in store:
        raise HTTPException(status_code=404, detail="Search ID not found")
    leads = store[search_id]["leads"]
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
