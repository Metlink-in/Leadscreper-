from __future__ import annotations

import importlib
import asyncio
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set

from app.models.lead import Lead
from app.services import serp_service

logger = logging.getLogger(__name__)


def _extract_contact_info(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract email, phone, and website from text."""
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text, re.IGNORECASE)
    email = email_match.group(0) if email_match else None

    phone_patterns = [
        r'\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{0,4}',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\d{10,15}',
        r'\+\d{10,15}',
    ]

    phone = None
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            phone = phone_match.group(0)
            phone = re.sub(r'[^\d+\-\(\)\s]', '', phone).strip()
            break

    website_pattern = r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9./_\-%]*)?'
    website_match = re.search(website_pattern, text)
    extracted_website = website_match.group(0).rstrip('.;,') if website_match else None

    return email, phone, extracted_website


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip()


def _extract_url(item: Dict[str, object], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _guess_platform(url: Optional[str]) -> Optional[str]:
    if not url: return None
    text = url.lower()
    platforms = {
        "upwork": "Upwork", "freelancer": "Freelancer", "linkedin": "LinkedIn",
        "indeed": "Indeed", "glassdoor": "Glassdoor", "angel": "AngelList",
        "youtube": "YouTube", "pinterest": "Pinterest", "tiktok": "TikTok",
        "github": "GitHub", "crunchbase": "Crunchbase", "facebook": "Facebook",
        "twitter": "Twitter/X", "x.com": "Twitter/X", "instagram": "Instagram", "reddit": "Reddit"
    }
    for key, val in platforms.items():
        if key in text: return val
    return None


def _keywords_matched(raw_keywords: Optional[List[str]], name: str, description: str) -> List[str]:
    if not raw_keywords: return []
    normalized = set()
    combined = f"{name} {description}".lower()
    for keyword in raw_keywords:
        if keyword and keyword.lower() in combined: normalized.add(keyword)
    return list(normalized)


def _make_base_lead(
    category: int,
    industry: str,
    source: str,
    source_url: str,
    name: str,
    description: str,
    location: str,
    keywords: Optional[List[str]],
    user_id: Optional[str] = None,
    website: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    platform: Optional[str] = None,
    post_url: Optional[str] = None,
) -> Lead:
    keywords_matched = _keywords_matched(keywords, name, description)
    if industry not in keywords_matched: keywords_matched.append(industry)

    extracted_email, extracted_phone, extracted_website = _extract_contact_info(f"{name} {description}")
    email = email or extracted_email
    phone = phone or extracted_phone
    website = website or extracted_website

    followers = None
    if website:
        ws_lower = website.lower()
        if "followers" in ws_lower:
            followers = website.strip()
            website = None
        elif _guess_platform(website) or "posts" in ws_lower or " " in website.strip():
            post_url = post_url or website
            website = None
        elif "." not in website:
            website = None

    return Lead(
        id=uuid.uuid4().hex,
        user_id=user_id,
        name=name,
        category=category,
        industry=industry,
        source=source,
        source_url=source_url,
        website=website,
        email=email,
        phone=phone,
        location=location,
        description=description,
        platform=platform,
        post_url=post_url,
        followers=followers,
        scraped_at=datetime.utcnow(),
        keywords_matched=keywords_matched,
    )


async def scrape_all(
    categories: List[int],
    industries: List[str],
    country: Optional[str],
    city: Optional[str],
    keywords: Optional[List[str]],
    platforms: Optional[List[str]] = None,
    max_results: int = 20,
    enable_ai: bool = True,
    user_id: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> List[Lead]:
    api_keys = api_keys or {}
    search_key = api_keys.get("search_api_key")
    gemini_key = api_keys.get("gemini_api_key")

    query_location = f"{city}, {country}" if city and country else (city or country or "")
    platform_query = " OR ".join([f"site:{p}.com" for p in platforms]) if platforms else ""
    
    leads: List[Lead] = []
    
    # Run searches for each category and industry
    for category in categories:
        for industry in industries:
            try:
                # Basic search logic consolidated
                q1 = f"{industry} companies contact email phone {query_location}".strip()
                q2 = f"{industry} tech firms contact {query_location} {platform_query}".strip()
                
                # Fetch from Maps and Search
                results = await asyncio.gather(
                    serp_service.search_google_maps(q1, location=query_location, api_key=search_key),
                    serp_service.search_google(q2, num=max_results, api_key=search_key),
                    return_exceptions=True
                )
                
                for res in results:
                    if isinstance(res, Exception):
                        from app.services.exceptions import APIError
                        if isinstance(res, APIError):
                            raise res
                        logger.error("[SCRAPE] Warning: Ignored sub-fetch exception: %s", res)
                    elif isinstance(res, list):
                        for item in res:
                            lead = _normalize_item(item, category, industry, country, city, keywords, user_id)
                            if lead: leads.append(lead)
            except Exception as e:
                logger.error("[SCRAPE] Error in task: %s", e)

    if enable_ai and leads:
        try:
            gemini_service = importlib.import_module("app.services.gemini_service")
            leads = await gemini_service.enrich_leads(leads, api_key=gemini_key)
        except Exception as exc:
            logger.warning("[AI] Enrichment failed: %s", exc)

    return leads

def _normalize_item(item: Dict[str, Any], category: int, industry: str, country: Optional[str], city: Optional[str], keywords: Optional[List[str]], user_id: str) -> Optional[Lead]:
    title = _normalize_text(item.get("title") or item.get("name") or "Unknown")
    link = _extract_url(item, ["link", "url", "website", "job_link"])
    snippet = _normalize_text(item.get("snippet") or item.get("description") or item.get("address") or "")
    location = _normalize_text(item.get("address") or (f"{city}, {country}" if city and country else (city or country or "Unknown")))
    
    return _make_base_lead(
        category=category,
        industry=industry,
        source="Google Search",
        source_url=link or "",
        name=title,
        description=snippet,
        location=location,
        keywords=keywords,
        user_id=user_id,
        website=link if link and "." in link else None,
        platform=_guess_platform(link)
    )
