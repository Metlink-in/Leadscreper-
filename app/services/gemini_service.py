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
    # Try to find JSON block
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Try generic code block
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
        
    # Just return text, maybe it's raw JSON
    return text.strip()

def _extract_contact_info_regex(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract email and phone from text using regex patterns."""
    # Email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text, re.IGNORECASE)
    email = email_match.group(0) if email_match else None

    # Phone pattern
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

async def _call_gemini_http(prompt: str) -> Optional[str]:
    """Call Gemini API via direct HTTP request to avoid SDK/grpcio compatibility issues."""
    if not settings.gemini_api_key:
        logger.warning("[AI] Gemini API key missing")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
    
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
                    logger.warning("[AI] Rate limit hit (429), retrying in %ds... (attempt %d/%d)", retry_delay, attempt + 1, max_retries)
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                # Extract text from response structure
                candidates = data.get("candidates", [])
                if candidates and candidates[0].get("content", {}).get("parts"):
                    return candidates[0]["content"]["parts"][0].get("text")
                
                logger.warning("[AI] Unexpected Gemini response structure: %s", data)
                return None
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error("[AI] Gemini API HTTP request failed after %d attempts: %s", max_retries, e)
            await asyncio.sleep(retry_delay)
            retry_delay *= 2
            
    return None

async def enrich_lead(lead: Lead) -> Lead:
    if not settings.enable_ai_enrichment or not settings.gemini_api_key:
        return lead

    # 1. Main Enrichment Analysis
    prompt = _build_enrichment_prompt(lead)
    text = await _call_gemini_http(prompt)
    
    if text:
        try:
            json_text = _extract_json(text)
            data = json.loads(json_text)
            
            lead.ai_score = int(data.get("score", 0))
            lead.ai_summary = data.get("summary")
            lead.outreach_angle = data.get("outreach_angle")
            lead.contact_priority = data.get("contact_priority")
            lead.lead_quality = data.get("lead_quality")

            # Extract additional contacts if found
            extracted_contacts = data.get("extracted_contacts", "")
            if extracted_contacts and isinstance(extracted_contacts, str):
                extracted_email, extracted_phone = _extract_contact_info_regex(extracted_contacts)
                if extracted_email and not lead.email:
                    lead.email = extracted_email
                if extracted_phone and not lead.phone:
                    lead.phone = extracted_phone
        except Exception as exc:
            logger.warning("[AI] Enrichment parsing failed for lead=%s: %s", lead.id, exc)

    # 2. Deep Contact Extraction if info is still missing
    if not lead.email or not lead.phone:
        try:
            email, phone, social, contact_page = await extract_contacts_with_ai(lead)
            if email and not lead.email: lead.email = email
            if phone and not lead.phone: lead.phone = phone
        except Exception as exc:
            logger.warning("[AI] Deep contact extraction failed for lead=%s: %s", lead.id, exc)

    return lead

async def enrich_leads(leads: List[Lead]) -> List[Lead]:
    if not leads:
        return leads
        
    semaphore = asyncio.Semaphore(2)  # Low concurrency for free-tier keys

    async def _enrich(lead: Lead) -> Lead:
        async with semaphore:
            return await enrich_lead(lead)

    logger.info("[AI] Enriching %d leads via HTTP API...", len(leads))
    results = await asyncio.gather(*[_enrich(lead) for lead in leads])
    return list(results)

async def extract_contacts_with_ai(lead: Lead) -> tuple[Optional[str], Optional[str], List[str], Optional[str]]:
    """Use AI to extract contact information from lead data."""
    if not settings.enable_ai_enrichment or not settings.gemini_api_key:
        return None, None, [], None

    prompt = _build_contact_extraction_prompt(lead)
    text = await _call_gemini_http(prompt)
    
    if text:
        try:
            json_text = _extract_json(text)
            data = json.loads(json_text)
            return (
                data.get("email"),
                data.get("phone"),
                data.get("social_links", []),
                data.get("contact_page")
            )
        except Exception as exc:
            logger.warning("[AI] Contact extraction parsing failed for lead=%s: %s", lead.id, exc)
            
    return None, None, [], None
