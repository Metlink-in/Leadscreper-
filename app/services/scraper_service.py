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
    """Extract email, phone, and website from text using comprehensive regex patterns."""
    import re

    # Enhanced email pattern - more comprehensive
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text, re.IGNORECASE)
    email = email_match.group(0) if email_match else None

    # Enhanced phone pattern - international formats
    phone_patterns = [
        r'\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{0,4}',  # +1 (123) 456-7890
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (123) 456-7890 or 123-456-7890
        r'\d{10,15}',  # 10-15 digit numbers
        r'\+\d{10,15}',  # + followed by 10-15 digits
    ]

    phone = None
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            phone = phone_match.group(0)
            # Clean up the phone number
            phone = re.sub(r'[^\d+\-\(\)\s]', '', phone).strip()
            break

    # Extract website URL (http/https)
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
    if not url:
        return None
    text = url.lower()
    if "upwork" in text:
        return "Upwork"
    if "freelancer" in text:
        return "Freelancer"
    if "linkedin" in text:
        return "LinkedIn"
    if "indeed" in text:
        return "Indeed"
    if "glassdoor" in text:
        return "Glassdoor"
    if "angel" in text:
        return "AngelList"
    if "youtube" in text:
        return "YouTube"
    if "pinterest" in text:
        return "Pinterest"
    if "tiktok" in text:
        return "TikTok"
    if "github" in text:
        return "GitHub"
    if "crunchbase" in text:
        return "Crunchbase"
    if "facebook" in text:
        return "Facebook"
    if "twitter" in text or "x.com" in text:
        return "Twitter/X"
    if "instagram" in text:
        return "Instagram"
    if "reddit" in text:
        return "Reddit"
    return None


def _keywords_matched(raw_keywords: Optional[List[str]], name: str, description: str) -> List[str]:
    if not raw_keywords:
        return []
    normalized = set()
    combined = f"{name} {description}".lower()
    for keyword in raw_keywords:
        if keyword and keyword.lower() in combined:
            normalized.add(keyword)
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
    website: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    platform: Optional[str] = None,
    post_url: Optional[str] = None,
) -> Lead:
    keywords_matched = _keywords_matched(keywords, name, description)
    if industry not in keywords_matched:
        keywords_matched.append(industry)

    # Extract contact info from description if not provided
    # Extract contact info and website from description
    extracted_email, extracted_phone, extracted_website = _extract_contact_info(f"{name} {description}")
    if not email:
        email = extracted_email
    if not phone:
        phone = extracted_phone
    if not website and extracted_website:
        website = extracted_website

    # If website is just a social profile, move it to post_url and clear website
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
        ai_score=None,
        ai_summary=None,
        outreach_angle=None,
        platform=platform,
        post_url=post_url,
        followers=followers,
        scraped_at=datetime.utcnow(),
        keywords_matched=keywords_matched,
    )


def _parse_source_terms(country: Optional[str], city: Optional[str]) -> str:
    if city and country:
        return f"{city}, {country}"
    if city:
        return city
    return country or ""


def _normalize_map_item(item: Dict[str, object], category: int, industry: str, country: Optional[str], city: Optional[str], keywords: Optional[List[str]]) -> Optional[Lead]:
    title = _normalize_text(item.get("title") or item.get("name") or "Unknown")
    address = _normalize_text(item.get("address") or item.get("address_lines") or "")
    phone = _normalize_text(item.get("phone"))
    website = _extract_url(item, ["website", "website_link"])
    source_url = _extract_url(item, ["link", "serpapi_link", "source"])
    description = _normalize_text(item.get("description") or item.get("snippet") or address)
    location = ", ".join(part for part in [address, _parse_source_terms(country, city)] if part)
    if not source_url:
        source_url = f"https://maps.google.com/?q={title.replace(' ', '+')}"
    return _make_base_lead(
        category=category,
        industry=industry,
        source="Google Maps",
        source_url=source_url,
        name=title,
        description=description,
        location=location or "Unknown",
        keywords=keywords,
        website=website,
        phone=phone or None,
    )


def _normalize_search_item(item: Dict[str, object], category: int, industry: str, country: Optional[str], city: Optional[str], keywords: Optional[List[str]], source_tag: str) -> Optional[Lead]:
    title = _normalize_text(item.get("title") or item.get("title_no_format") or item.get("name") or "Unknown")
    link = _extract_url(item, ["link", "url", "displayed_link", "formatted_url"])
    snippet = _normalize_text(item.get("snippet") or item.get("description") or item.get("snippet_highlighted") or "")
    location = _parse_source_terms(country, city)
    return _make_base_lead(
        category=category,
        industry=industry,
        source=source_tag,
        source_url=link or "",
        name=title,
        description=snippet,
        location=location or "Unknown",
        keywords=keywords,
        website=_extract_url(item, ["website", "displayed_link", "domain"]),
        platform=_guess_platform(link),
        post_url=link,
    )


def _normalize_job_item(item: Dict[str, object], category: int, industry: str, country: Optional[str], city: Optional[str], keywords: Optional[List[str]]) -> Optional[Lead]:
    title = _normalize_text(item.get("title") or item.get("position_title") or "Freelance Opportunity")
    link = _extract_url(item, ["link", "job_link", "url"])
    snippet = _normalize_text(item.get("snippet") or item.get("description") or item.get("summary") or "")
    location = _parse_source_terms(country, city)
    platform = _guess_platform(link)
    return _make_base_lead(
        category=category,
        industry=industry,
        source="Google Jobs",
        source_url=link or "",
        name=title,
        description=snippet,
        location=location or "Unknown",
        keywords=keywords,
        website=_extract_url(item, ["website", "domain"]),
        platform=platform,
        post_url=link,
    )


async def _scrape_category_one(industry: str, country: Optional[str], city: Optional[str], keywords: Optional[List[str]], platforms: Optional[List[str]], max_results: int) -> List[Lead]:
    query_location = _parse_source_terms(country, city)
    platform_query = " OR ".join([f"site:{p}.com" for p in platforms]) if platforms else ""
    
    # Enhanced queries focused on contact details and business information
    base_map = f"{industry} companies contact email phone website"
    if query_location: base_map += f" {query_location}"
    
    base_search1 = f"{industry} companies directory contact details"
    if query_location: base_search1 += f" {query_location}"
    if platform_query: base_search1 += f" ({platform_query})"
    
    base_search2 = f"top {industry} businesses email phone contact"
    if query_location: base_search2 += f" {query_location}"
    if platform_query: base_search2 += f" ({platform_query})"
    
    base_search3 = f"{industry} firms contact information"
    if query_location: base_search3 += f" {query_location}"
    if platform_query: base_search3 += f" ({platform_query})"

    maps_task = serp_service.search_google_maps(base_map, location=query_location)
    search_tasks = [
        serp_service.search_google(base_search1, num=max_results // 3),
        serp_service.search_google(base_search2, num=max_results // 3),
        serp_service.search_google(base_search3, num=max_results // 3),
    ]

    map_results, *search_results_list = await asyncio.gather(maps_task, *search_tasks)
    search_results = [item for sublist in search_results_list for item in sublist]

    leads = [
        _normalize_map_item(item, 1, industry, country, city, keywords)
        for item in map_results
    ]
    leads.extend(
        _normalize_search_item(item, 1, industry, country, city, keywords, "Google Search")
        for item in search_results
    )
    return [lead for lead in leads if lead and lead.source_url]


async def _scrape_category_two(industry: str, country: Optional[str], city: Optional[str], keywords: Optional[List[str]], platforms: Optional[List[str]], max_results: int) -> List[Lead]:
    query_location = _parse_source_terms(country, city)
    platform_query = " OR ".join([f"site:{p}.com" for p in platforms]) if platforms else ""
    
    # Enhanced queries focused on tech companies with contact details
    search_query_a = f"{industry} startup contact email phone website"
    if query_location: search_query_a += f" {query_location}"
    if platform_query: search_query_a += f" ({platform_query})"

    search_query_b = f"{industry} company software development outsourcing contact details"
    if query_location: search_query_b += f" {query_location}"
    if platform_query: search_query_b += f" ({platform_query})"

    search_query_c = f"{industry} tech firms email phone contact information"
    if query_location: search_query_c += f" {query_location}"
    if platform_query: search_query_c += f" ({platform_query})"

    jobs_query = f"{industry} software developer jobs contact email"
    if query_location: jobs_query += f" {query_location}"
    if platform_query: jobs_query += f" ({platform_query})"

    result_a, result_b, result_c, jobs_results = await asyncio.gather(
        serp_service.search_google(search_query_a, num=max_results // 3),
        serp_service.search_google(search_query_b, num=max_results // 3),
        serp_service.search_google(search_query_c, num=max_results // 3),
        serp_service.search_google_jobs(jobs_query, location=query_location),
    )
    leads: List[Lead] = []
    leads.extend(
        _normalize_search_item(item, 2, industry, country, city, keywords, "Google Search")
        for item in result_a
    )
    leads.extend(
        _normalize_search_item(item, 2, industry, country, city, keywords, "Google Search")
        for item in result_b
    )
    leads.extend(
        _normalize_search_item(item, 2, industry, country, city, keywords, "Google Search")
        for item in result_c
    )
    leads.extend(
        _normalize_job_item(item, 2, industry, country, city, keywords)
        for item in jobs_results
    )
    return [lead for lead in leads if lead and lead.source_url]


async def _scrape_category_three(industry: str, country: Optional[str], city: Optional[str], keywords: Optional[List[str]], platforms: Optional[List[str]], max_results: int) -> List[Lead]:
    query_location = _parse_source_terms(country, city)
    # More targeted freelance project searches
    if platforms:
        platform_query = " OR ".join([f"site:{p}.com" for p in platforms])
        search_query_a = f"({platform_query}) \"{industry} project\" OR \"looking for developer\" contact {query_location}".strip()
    else:
        search_query_a = f"site:upwork.com OR site:freelancer.com OR site:linkedin.com \"{industry} project\" OR \"looking for developer\" contact {query_location}".strip()
    search_query_b = f"{industry} freelance project needed contact email {query_location}" if query_location else f"{industry} freelance project needed contact email"
    jobs_query = f"{industry} freelance developer project contact {query_location}" if query_location else f"{industry} freelance developer project contact"
    result_a, result_b, jobs_results = await asyncio.gather(
        serp_service.search_google(search_query_a, num=max_results),
        serp_service.search_google(search_query_b, num=max_results),
        serp_service.search_google_jobs(jobs_query, location=query_location),
    )
    leads: List[Lead] = []
    leads.extend(
        _normalize_search_item(item, 3, industry, country, city, keywords, "Google Search")
        for item in result_a
    )
    leads.extend(
        _normalize_search_item(item, 3, industry, country, city, keywords, "Google Search")
        for item in result_b
    )
    leads.extend(
        _normalize_job_item(item, 3, industry, country, city, keywords)
        for item in jobs_results
    )
    for lead in leads:
        if lead and lead.platform is None:
            lead.platform = _guess_platform(lead.source_url)
    return [lead for lead in leads if lead and lead.source_url]


async def _scrape_category_four(industry: str, country: Optional[str], city: Optional[str], keywords: Optional[List[str]], platforms: Optional[List[str]], max_results: int) -> List[Lead]:
    query_location = _parse_source_terms(country, city)
    platform_query = " OR ".join([f"site:{p}.com" for p in platforms]) if platforms else ""
    
    # More specific agency searches with contact info
    search_query_a = f"AI development agency contact email phone"
    if query_location: search_query_a += f" {query_location}"
    if platform_query: search_query_a += f" ({platform_query})"

    search_query_b = f"software development agency portfolio contact"
    if query_location: search_query_b += f" {query_location}"
    if platform_query: search_query_b += f" ({platform_query})"
    result_a, result_b = await asyncio.gather(
        serp_service.search_google(search_query_a, num=max_results),
        serp_service.search_google(search_query_b, num=max_results),
    )
    leads: List[Lead] = []
    leads.extend(
        _normalize_search_item(item, 4, industry, country, city, keywords, "Google Search")
        for item in result_a
    )
    leads.extend(
        _normalize_search_item(item, 4, industry, country, city, keywords, "Google Search")
        for item in result_b
    )
    return [lead for lead in leads if lead and lead.source_url]


async def scrape_all(
    categories: List[int],
    industries: List[str],
    country: Optional[str],
    city: Optional[str],
    keywords: Optional[List[str]],
    platforms: Optional[List[str]] = None,
    max_results: int = 20,
    enable_ai: bool = True,
) -> List[Lead]:
    category_map = {
        1: _scrape_category_one,
        2: _scrape_category_two,
        3: _scrape_category_three,
        4: _scrape_category_four,
    }
    tasks: List[asyncio.Task[List[Lead]]] = []
    for category in categories:
        handler = category_map.get(category)
        if not handler:
            continue
        for industry in industries:
            tasks.append(asyncio.create_task(handler(industry, country, city, keywords, platforms or [], max_results)))

    logger.info(
        "[SCRAPE] Starting %d scraping task(s) | categories=%s | industries=%s | country=%s | city=%s",
        len(tasks), categories, industries, country, city,
    )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    leads: List[Lead] = []
    failed = 0
    for result in results:
        if isinstance(result, Exception):
            logger.warning("[SCRAPE] Scraping task failed: %s", result)
            failed += 1
            continue
        leads.extend(result)

    logger.info(
        "[SCRAPE] Raw leads collected: %d | failed tasks: %d",
        len(leads), failed,
    )

    if enable_ai:
        try:
            gemini_service = importlib.import_module("app.services.gemini_service")
            if hasattr(gemini_service, "enrich_leads"):
                logger.info("[AI] Starting AI enrichment for %d leads ...", len(leads))
                leads = await gemini_service.enrich_leads(leads)
                logger.info("[AI] AI enrichment complete. %d leads returned.", len(leads))
        except Exception as exc:
            logger.warning("[AI] AI enrichment disabled: %s", exc)
    else:
        logger.info("[SCRAPE] AI enrichment skipped (enable_ai=False)")

    if not leads:
        logger.warning(
            "[SCRAPE] ⚠️  No leads were collected! "
            "Check for CREDITS EXHAUSTED or MISSING KEY messages above."
        )

    return leads
