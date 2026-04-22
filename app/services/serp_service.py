from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.exceptions import APIError

logger = logging.getLogger(__name__)


async def _execute_search(params: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Execute a search against SearchApi.io."""
    effective_key = api_key or settings.search_api_key
    if not effective_key:
        raise APIError("SearchApi.io key is missing. Please add it in your Settings.", 401)

    params["api_key"] = effective_key
    base_url = "https://www.searchapi.io/api/v1/search"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(base_url, params=params)
            
            if response.status_code == 200:
                return response.json()
            
            if response.status_code == 402:
                raise APIError("Credits exhausted on SearchApi.io. Please upgrade your plan.", 402)
            
            if response.status_code == 429:
                error_data = response.json()
                error_msg = error_data.get("error", "Rate limit exceeded on SearchApi.io")
                raise APIError(error_msg, 429)
                
            if response.status_code == 401:
                raise APIError("Invalid SearchApi.io key. Please check your credentials.", 401)

            raise APIError(f"SearchApi.io error: {response.status_code}", response.status_code)

        except httpx.RequestError as exc:
            logger.error("[SEARCH] Connection error: %s", exc)
            raise APIError(f"Connection failed: {str(exc)}", 500)


async def search_google(query: str, num: int = 10, page: int = 1, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Perform a standard Google search via SearchApi.io."""
    logger.info("[SEARCH] Google search | query=%r | page=%d", query, page)
    try:
        params = {
            "engine": "google",
            "q": query,
            "num": num,
            "page": page,
        }
        result = await _execute_search(params, api_key=api_key)
        items = result.get("organic_results", []) or []
        logger.info("[SEARCH] Google returned %d results", len(items))
        return items
    except Exception as exc:
        logger.warning("[SEARCH] Google search FAILED | query=%r | error: %s", query, exc)
        if isinstance(exc, APIError):
            raise
        return []


async def search_google_maps(query: str, location: Optional[str] = None, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Perform a Google Maps search via SearchApi.io."""
    logger.info("[MAPS] Google Maps search | query=%r", query)
    try:
        params: Dict[str, Any] = {
            "engine": "google_maps",
            "q": query,
            "hl": "en",
        }
        if location:
            params["location"] = location
            
        result = await _execute_search(params, api_key=api_key)
        items = result.get("local_results", []) or result.get("results", []) or []
        logger.info("[MAPS] Google Maps returned %d results", len(items))
        return items
    except Exception as exc:
        logger.warning("[MAPS] Google Maps search FAILED | query=%r | error: %s", query, exc)
        if isinstance(exc, APIError):
            raise
        return []


async def search_google_jobs(query: str, location: Optional[str] = None, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Perform a Google Jobs search via SearchApi.io."""
    logger.info("[JOBS] Google Jobs search | query=%r", query)
    try:
        params: Dict[str, Any] = {
            "engine": "google_jobs",
            "q": query,
            "hl": "en",
        }
        if location:
            params["location"] = location
            
        result = await _execute_search(params, api_key=api_key)
        items = result.get("jobs", []) or result.get("jobs_results", []) or result.get("results", []) or []
        logger.info("[JOBS] Google Jobs returned %d results", len(items))
        return items
    except Exception as exc:
        logger.warning("[JOBS] Google Jobs search FAILED | query=%r | error: %s", query, exc)
        if isinstance(exc, APIError):
            raise
        return []


async def get_account_info(override_key: Optional[str] = None) -> Dict[str, Any]:
    """Fetch account info including credits from SearchApi.io."""
    api_key = override_key or settings.search_api_key
    if not api_key:
        return {"error": "API key missing"}
    
    url = f"https://www.searchapi.io/api/v1/me?api_key={api_key}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                return {
                    "remaining_searches": data.get("account", {}).get("remaining_credits"),
                    "plan_name": data.get("subscription", {}).get("plan_name", "Free"),
                }
            return {"error": f"API Error: {response.status_code}"}
        except Exception as e:
            logger.error("[ACCOUNT] Failed to fetch account info: %s", e)
            return {"error": str(e)}
