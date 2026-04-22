import asyncio
import httpx
import json

async def test_search():
    API_KEY = "AUTxV81WPCAHpWp3Kowi1w15"
    base_url = "https://www.searchapi.io/api/v1/search"
    
    params1 = {"engine": "google", "q": "Software tech firms contact USA", "num": 10, "api_key": API_KEY}
    params2 = {"engine": "google_maps", "q": "Software companies contact email phone USA", "location": "Austin", "api_key": API_KEY}
    
    async with httpx.AsyncClient() as client:
        r1 = await client.get(base_url, params=params1)
        print("GOOGLE STATUS:", r1.status_code)
        if r1.status_code == 200:
            data = r1.json()
            print("KEYS:", data.keys())
            organic = data.get("organic_results", [])
            print("ORGANIC RESULTS COUNT:", len(organic))
            if organic: print(organic[0].keys())
        else:
            print("ERROR", r1.text)
            
        r2 = await client.get(base_url, params=params2)
        print("\nMAPS STATUS:", r2.status_code)
        if r2.status_code == 200:
            data = r2.json()
            print("KEYS:", data.keys())
            local = data.get("local_results", [])
            print("LOCAL RESULTS COUNT:", len(local))
            if local: print(local[0].keys())

if __name__ == "__main__":
    asyncio.run(test_search())
