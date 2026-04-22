from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _use_searchapi() -> bool:
    return settings.search_api_provider.lower() == "searchapi"


def _get_api_key() -> Optional[str]:
    return settings.search_api_key or settings.serp_api_key


async def _execute_search(params: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.search_api_base_url if _use_searchapi() else "https://serpapi.com"
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        response = await client.get("/search", params=params)
        response.raise_for_status()
        return response.json()


async def search_google(query: str, num: int = 20, location: Optional[str] = None) -> List[Dict[str, Any]]:
    api_key = _get_api_key()
    if not api_key:
        logger.warning("Missing search API key for provider %s", settings.search_api_provider)
        return []

    try:
        if _use_searchapi():
            all_results: List[Dict[str, Any]] = []
            pages = max(1, (num + 9) // 10)
            for page in range(1, pages + 1):
                params: Dict[str, Any] = {
                    "engine": "google",
                    "q": query,
                    "api_key": api_key,
                    "hl": "en",
                    "page": page,
                }
                if location:
                    params["location"] = location
                result = await _execute_search(params)
                items = result.get("organic_results", []) or []
                all_results.extend(items)
                if not items:
                    break
            return all_results[:num]

        params = {
            "engine": "google",
            "q": query,
            "num": num,
            "api_key": api_key,
            "hl": "en",
        }
        if location:
            params["location"] = location
        result = await _execute_search(params)
        return result.get("organic_results", []) or []
    except Exception as exc:
        logger.warning("Google search failed for query=%s: %s", query, exc)
        return []


async def search_google_maps(query: str, location: Optional[str] = None) -> List[Dict[str, Any]]:
    api_key = _get_api_key()
    if not api_key:
        logger.warning("Missing search API key for provider %s", settings.search_api_provider)
        return []

    try:
        if _use_searchapi():
            params: Dict[str, Any] = {
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "hl": "en",
            }
            if location:
                params["location"] = location
            result = await _execute_search(params)
            return result.get("local_results", []) or []

        params = {
            "engine": "google_maps",
            "q": query,
            "api_key": api_key,
            "hl": "en",
        }
        if location:
            params["location"] = location
        result = await _execute_search(params)
        return result.get("local_results", []) or []
    except Exception as exc:
        logger.warning("Google Maps search failed for query=%s: %s", query, exc)
        return []


async def search_google_jobs(query: str, location: Optional[str] = None) -> List[Dict[str, Any]]:
    api_key = _get_api_key()
    if not api_key:
        logger.warning("Missing search API key for provider %s", settings.search_api_provider)
        return []

    try:
        if _use_searchapi():
            params: Dict[str, Any] = {
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "hl": "en",
            }
            if location:
                params["location"] = location
            result = await _execute_search(params)
            return result.get("jobs", []) or result.get("job_results", []) or result.get("jobs_results", []) or []

        params = {
            "engine": "google_jobs",
            "q": query,
            "api_key": api_key,
            "hl": "en",
        }
        if location:
            params["location"] = location
        result = await _execute_search(params)
        return result.get("jobs_results", []) or result.get("job_results", []) or []
    except Exception as exc:
        logger.warning("Google Jobs search failed for query=%s: %s", query, exc)
        return []
