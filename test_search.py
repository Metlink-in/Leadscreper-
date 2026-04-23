import asyncio
import httpx
from app.services.db_service import db_service

async def test_search():
    await db_service.connect()
    user = await db_service.get_user_by_email("jiteshbawaskar05@gmail.com")
    await db_service.disconnect()
    
    if not user:
        print("User not found")
        return

    payload = {
        "categories": [1, 2],
        "industries": ["Technology", "Software", "Information"],
        "country": "United States",
        "city": "",
        "platforms": [],
        "max_results": 10,
        "enable_ai": False # keep false for faster testing, or true to test gemini
    }

    print(f"Sending search request with payload: {payload}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # We need a cookie or we need to hit the endpoint directly.
        # Wait, the endpoint requires authentication. 
        pass

    # Actually, it's easier to just call the scrape_all function directly for testing.
    from app.services.scraper_service import scrape_all
    
    api_keys = {
        "search_api_key": user.get("search_api_key"),
        "gemini_api_key": user.get("gemini_api_key")
    }
    
    print("Executing scrape_all...")
    leads = await scrape_all(
        categories=payload["categories"],
        industries=payload["industries"],
        country=payload["country"],
        city=payload["city"],
        keywords=[],
        platforms=payload["platforms"],
        max_results=payload["max_results"],
        enable_ai=payload["enable_ai"],
        user_id=str(user["_id"]),
        api_keys=api_keys
    )
    
    print(f"Scrape finished. Found {len(leads)} leads.")
    if leads:
        for i, lead in enumerate(leads[:3]):
            print(f"Lead {i+1}: {lead.name} - {lead.industry} - {lead.source_url}")

if __name__ == "__main__":
    asyncio.run(test_search())
