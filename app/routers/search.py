from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks

from app.config import settings
from app.models.search import SearchRequest
from app.services.scraper_service import scrape_all
from app.services.db_service import db_service
from app.services.exceptions import APIError

from app.services.dependencies import require_user

router = APIRouter()
logger = logging.getLogger(__name__)

async def run_search_task(search_id: str, request: SearchRequest, user_id: str, api_keys: dict):
    """Background task to perform the search and save results."""
    try:
        max_results = min(request.max_results or settings.max_results_per_source, settings.max_results_per_source)
        leads = await scrape_all(
            categories=request.categories,
            industries=request.industries,
            country=request.country,
            city=request.city,
            keywords=request.keywords,
            platforms=request.platforms,
            max_results=max_results,
            enable_ai=request.enable_ai,
            user_id=user_id,
            api_keys=api_keys
        )
        
        scored_leads = [lead for lead in leads if lead.ai_score is not None]
        unscored_leads = [lead for lead in leads if lead.ai_score is None]
        scored_leads.sort(key=lambda x: x.ai_score or 0, reverse=True)
        sorted_leads = scored_leads + unscored_leads

        db_search_data = {
            "created_at": datetime.utcnow().isoformat(),
            "meta": {
                "categories": request.categories,
                "industries": request.industries,
                "country": request.country,
                "city": request.city,
                "keywords": request.keywords,
                "platforms": request.platforms,
                "max_results": max_results,
                "enable_ai": request.enable_ai,
            },
            "leads": [lead.model_dump() for lead in sorted_leads],
            "status": "completed",
            "summary": {
                "high_priority_leads": len([l for l in scored_leads if (l.ai_score or 0) >= 70]),
                "leads_with_contacts": len([l for l in sorted_leads if l.email or l.phone]),
                "total_leads": len(sorted_leads)
            }
        }
        await db_service.save_search(search_id, db_search_data, user_id=user_id)
        logger.info("[TASK] Search %s completed successfully.", search_id)
        
    except Exception as exc:
        logger.error("[TASK] Search %s failed: %s", search_id, exc, exc_info=True)
        # Update status to failed so UI can stop polling
        await db_service.save_search(search_id, {
            "status": "failed",
            "error": str(exc),
            "created_at": datetime.utcnow().isoformat()
        }, user_id=user_id)

@router.post("/api/search")
async def search(request: SearchRequest, background_tasks: BackgroundTasks, user = Depends(require_user)) -> dict:
    logger.info(
        "[REQUEST] POST /api/search | user=%s | industries=%s | categories=%s",
        user["email"], request.industries, request.categories,
    )
    
    api_keys = {
        "search_api_key": user.get("search_api_key"),
        "gemini_api_key": user.get("gemini_api_key"),
        "openai_api_key": user.get("openai_api_key"),
    }
    
    search_id = uuid4().hex
    
    # Initialize placeholder in DB
    placeholder = {
        "status": "processing",
        "created_at": datetime.utcnow().isoformat(),
        "meta": {
            "categories": request.categories,
            "industries": request.industries,
            "country": request.country,
            "city": request.city,
            "keywords": request.keywords,
            "enable_ai": request.enable_ai,
        },
        "leads": []
    }
    await db_service.save_search(search_id, placeholder, user_id=str(user["_id"]))
    
    # Start background task
    background_tasks.add_task(
        run_search_task, 
        search_id, 
        request, 
        str(user["_id"]), 
        api_keys
    )
    
    return {
        "search_id": search_id,
        "status": "processing",
        "message": "Search started in background"
    }

@router.get("/api/history")
async def get_history(limit: int = 50, user = Depends(require_user)) -> dict:
    try:
        history = await db_service.get_search_history(user_id=str(user["_id"]), limit=limit)
        return {"history": history}
    except Exception as exc:
        logger.error("[REQUEST] /api/history failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch history")

@router.get("/api/history/{search_id}")
async def get_history_detail(search_id: str, user = Depends(require_user)) -> dict:
    try:
        data = await db_service.get_search(search_id, user_id=str(user["_id"]))
        if not data:
            raise HTTPException(status_code=404, detail="Search not found")
            
        return {
            "search_id": search_id,
            "created_at": data.get("created_at"),
            "meta": data.get("meta"),
            "status": data.get("status", "completed"), # Default to completed for old records
            "total": len(data.get("leads", [])),
            "leads": data.get("leads", [])
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[REQUEST] /api/history/%s failed: %s", search_id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch history detail")

@router.delete("/api/history/{search_id}")
async def delete_search_history(search_id: str, user = Depends(require_user)):
    try:
        success = await db_service.delete_search(search_id, user_id=str(user["_id"]))
        if not success:
            raise HTTPException(status_code=404, detail="Search not found")
        return {"status": "success", "message": "Search deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[REQUEST] DELETE /api/history/%s failed: %s", search_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete search")

@router.delete("/api/history")
async def clear_all_history(user = Depends(require_user)):
    try:
        count = await db_service.clear_all_searches(user_id=str(user["_id"]))
        return {"status": "success", "message": f"Cleared {count} searches"}
    except Exception as exc:
        logger.error("[REQUEST] DELETE /api/history failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to clear history")
