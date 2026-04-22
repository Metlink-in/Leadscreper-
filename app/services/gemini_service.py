from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from app.config import settings
from app.models.lead import Lead

logger = logging.getLogger(__name__)

def _extract_json(text: str) -> str:
    """Robustly extract JSON from text, even if wrapped in markdown code blocks."""
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def _extract_contact_info_regex(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract email and phone from text using regex patterns."""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text, re.IGNORECASE)
    email = email_match.group(0) if email_match else None

    phone_patterns = [
        r'\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{0,4}',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\b\d{10,15}\b',
    ]

    phone = None
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            phone = phone_match.group(0)
            phone = re.sub(r'[^\d+\-\(\)\s]', '', phone).strip()
            break

    return email, phone

def _build_enrichment_prompt(lead: Lead) -> str:
    lead_json = json.dumps(lead.model_dump(), default=str)
    return (
        "You are a business development assistant for an AI/software development agency. "
        "Analyze this lead and provide actionable insights for outreach.\n\n"
        f"Lead data: {lead_json}\n\n"
        "Focus on extracting and analyzing contact information and business needs. Return JSON with:\n"
        "- score: integer 0-100 (how likely they need custom dev/AI services based on their industry, description, and keywords)\n"
        "- summary: 1-2 sentence concise summary of who they are, what they do, and their specific tech needs\n"
        "- outreach_angle: 1 specific, compelling outreach angle with a clear value proposition and call-to-action\n"
        "- contact_priority: 'high', 'medium', or 'low' based on data completeness and business urgency\n"
        "- lead_quality: 'excellent', 'good', 'fair', or 'poor' based on contact info availability and relevance\n"
        "- extracted_contacts: any additional email/phone/website found in the description\n"
        "- tech_stack_indicators: mention of specific technologies they use or need\n"
        "Only return valid JSON, no markdown or extra text."
    )

def _build_contact_extraction_prompt(lead: Lead) -> str:
    return (
        "Extract ALL contact information from this business lead. Be thorough.\n\n"
        f"Business Name: {lead.name}\n"
        f"Description: {lead.description}\n"
        f"Website: {lead.website or 'Not provided'}\n"
        f"Source URL: {lead.source_url}\n"
        f"Location: {lead.location}\n"
        f"Industry: {lead.industry}\n\n"
        "Return JSON with:\n"
        "- email: primary email address found, or null\n"
        "- phone: primary phone number found, or null\n"
        "- social_links: array of all social media URLs found\n"
        "- contact_page: URL to contact page or form if found\n"
        "- additional_contacts: any other contact methods found\n"
        "Only return valid JSON, no markdown or extra text."
    )

async def _call_gemini_http(prompt: str, api_key: Optional[str] = None) -> Optional[str]:
    """Call Gemini API via direct HTTP request."""
    effective_key = api_key or settings.gemini_api_key
    if not effective_key:
        logger.warning("[AI] Gemini API key missing")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={effective_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 1024,
        }
    }

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 429:
                    logger.warning("[AI] Rate limit hit (429), retrying in %ds...", retry_delay)
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates and candidates[0].get("content", {}).get("parts"):
                    return candidates[0]["content"]["parts"][0].get("text")
                return None
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error("[AI] Gemini API failed: %s", e)
            await asyncio.sleep(retry_delay)
            retry_delay *= 2
    return None

async def enrich_lead(lead: Lead, api_key: Optional[str] = None) -> Lead:
    if not settings.enable_ai_enrichment:
        return lead
    
    effective_key = api_key or settings.gemini_api_key
    if not effective_key:
        return lead

    prompt = _build_enrichment_prompt(lead)
    text = await _call_gemini_http(prompt, api_key=effective_key)
    
    if text:
        try:
            json_text = _extract_json(text)
            data = json.loads(json_text)
            lead.ai_score = int(data.get("score", 0))
            lead.ai_summary = data.get("summary")
            lead.outreach_angle = data.get("outreach_angle")
            lead.contact_priority = data.get("contact_priority")
            lead.lead_quality = data.get("lead_quality")
            
            extracted_contacts = data.get("extracted_contacts", "")
            if extracted_contacts and isinstance(extracted_contacts, str):
                extracted_email, extracted_phone = _extract_contact_info_regex(extracted_contacts)
                if extracted_email and not lead.email: lead.email = extracted_email
                if extracted_phone and not lead.phone: lead.phone = extracted_phone
        except Exception as exc:
            logger.warning("[AI] Parsing failed: %s", exc)

    if not lead.email or not lead.phone:
        try:
            email, phone, social, contact_page = await extract_contacts_with_ai(lead, api_key=effective_key)
            if email and not lead.email: lead.email = email
            if phone and not lead.phone: lead.phone = phone
        except Exception:
            pass

    return lead

async def enrich_leads(leads: List[Lead], api_key: Optional[str] = None) -> List[Lead]:
    if not leads: return leads
    semaphore = asyncio.Semaphore(2)
    async def _enrich(lead: Lead) -> Lead:
        async with semaphore:
            return await enrich_lead(lead, api_key=api_key)
    logger.info("[AI] Enriching %d leads...", len(leads))
    results = await asyncio.gather(*[_enrich(lead) for lead in leads])
    return list(results)

async def extract_contacts_with_ai(lead: Lead, api_key: Optional[str] = None) -> tuple[Optional[str], Optional[str], List[str], Optional[str]]:
    """Use AI to extract contact information."""
    effective_key = api_key or settings.gemini_api_key
    if not effective_key:
        return None, None, [], None

    prompt = _build_contact_extraction_prompt(lead)
    text = await _call_gemini_http(prompt, api_key=effective_key)
    if text:
        try:
            json_text = _extract_json(text)
            data = json.loads(json_text)
            return (data.get("email"), data.get("phone"), data.get("social_links", []), data.get("contact_page"))
        except Exception:
            pass
    return None, None, [], None
