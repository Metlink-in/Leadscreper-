from __future__ import annotations

import asyncio
import importlib
import json
import logging
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.lead import Lead

logger = logging.getLogger(__name__)
_generativeai: Optional[Any] = None
_generativeai_loaded = False
_generativeai_error: Optional[BaseException] = None


def _extract_contact_info(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract email and phone from text using comprehensive regex patterns."""
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

    return email, phone


def _load_generativeai() -> Optional[Any]:
    global _generativeai, _generativeai_loaded, _generativeai_error
    if _generativeai_loaded:
        return _generativeai
    _generativeai_loaded = True
    try:
        _generativeai = importlib.import_module("google.generativeai")
        if settings.gemini_api_key:
            _generativeai.configure(api_key=settings.gemini_api_key)
        return _generativeai
    except BaseException as exc:
        _generativeai_error = exc
        logger.warning("Gemini SDK unavailable: %s", exc)
        return None


def _extract_text(response: Any) -> str:
    if isinstance(response, dict):
        content = response.get("content") or response.get("text") or response.get("output")
        if isinstance(content, list):
            return "".join(str(item.get("text", item)) for item in content)
        return str(content or "")
    if hasattr(response, "text"):
        return str(response.text)
    if hasattr(response, "content"):
        return str(response.content)
    return str(response)


def _build_prompt(lead: Lead) -> str:
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


async def _call_gemini(prompt: str) -> Dict[str, Any]:
    generativeai = _load_generativeai()
    if not generativeai:
        raise RuntimeError("Gemini SDK is unavailable")
    model = generativeai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response


async def enrich_lead(lead: Lead) -> Lead:
    if not settings.enable_ai_enrichment or not settings.gemini_api_key:
        return lead

    # First, enrich with analysis
    prompt = _build_prompt(lead)
    try:
        raw_response = await _call_gemini(prompt)
        text = _extract_text(raw_response)
        data = json.loads(text)
        lead.ai_score = int(data.get("score", 0))
        lead.ai_summary = data.get("summary")
        lead.outreach_angle = data.get("outreach_angle")
        lead.contact_priority = data.get("contact_priority")
        lead.lead_quality = data.get("lead_quality")

        # Extract additional contacts if found
        extracted_contacts = data.get("extracted_contacts", "")
        if extracted_contacts and isinstance(extracted_contacts, str):
            # Try to extract email and phone from the extracted contacts
            extracted_email, extracted_phone = _extract_contact_info(extracted_contacts)
            if extracted_email and not lead.email:
                lead.email = extracted_email
            if extracted_phone and not lead.phone:
                lead.phone = extracted_phone

    except Exception as exc:
        logger.warning("Gemini enrichment skipped for lead=%s: %s", lead.id, exc)

    # Then try to extract contact information if missing
    if not lead.email or not lead.phone:
        try:
            extracted_email, extracted_phone, social_links, contact_page = await extract_contacts_with_ai(lead)
            if extracted_email and not lead.email:
                lead.email = extracted_email
            if extracted_phone and not lead.phone:
                lead.phone = extracted_phone
            # Could add social_links and contact_page to lead model if needed
        except Exception as exc:
            logger.warning("Contact extraction failed for lead=%s: %s", lead.id, exc)

    return lead


async def enrich_leads(leads: List[Lead]) -> List[Lead]:
    semaphore = asyncio.Semaphore(3)  # Reduced concurrency for more thorough processing

    async def _enrich(lead: Lead) -> Lead:
        async with semaphore:
            return await enrich_lead(lead)

    return await asyncio.gather(*[_enrich(lead) for lead in leads])


def _build_contact_extraction_prompt(lead: Lead) -> str:
    return (
        "Extract ALL contact information from this business lead. Be thorough and look for any emails, phone numbers, "
        "social media links, or contact pages mentioned anywhere in the provided information.\n\n"
        f"Business Name: {lead.name}\n"
        f"Description: {lead.description}\n"
        f"Website: {lead.website or 'Not provided'}\n"
        f"Source URL: {lead.source_url}\n"
        f"Location: {lead.location}\n"
        f"Industry: {lead.industry}\n\n"
        "Search carefully for:\n"
        "- Email addresses (look for @ symbols, contact forms, mailto: links)\n"
        "- Phone numbers (various formats: +1-123-456-7890, (123) 456-7890, etc.)\n"
        "- Social media profiles (LinkedIn, Twitter, Facebook, Instagram, etc.)\n"
        "- Contact pages or forms\n"
        "- Any other contact methods mentioned\n\n"
        "Return JSON with:\n"
        "- email: primary email address found, or null\n"
        "- phone: primary phone number found, or null\n"
        "- social_links: array of all social media URLs found\n"
        "- contact_page: URL to contact page or form if found\n"
        "- additional_contacts: any other contact methods found\n"
        "Only return valid JSON, no markdown or extra text."
    )


async def extract_contacts_with_ai(lead: Lead) -> tuple[Optional[str], Optional[str], List[str], Optional[str]]:
    """Use AI to extract contact information from lead data."""
    if not settings.enable_ai_enrichment or not settings.gemini_api_key:
        return None, None, [], None

    prompt = _build_contact_extraction_prompt(lead)
    try:
        raw_response = await _call_gemini(prompt)
        text = _extract_text(raw_response)
        data = json.loads(text)
        return (
            data.get("email"),
            data.get("phone"),
            data.get("social_links", []),
            data.get("contact_page")
        )
    except Exception as exc:
        logger.warning("Contact extraction failed for lead=%s: %s", lead.id, exc)
        return None, None, [], None
