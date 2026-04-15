from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from typing import List, Optional
from mangum import Mangum

load_dotenv()

app = FastAPI(title="LeadScraper AI - Agency Edition")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys from .env
SERP_API_KEY = os.getenv("SERP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Setup Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

@app.get("/")
def read_root():
    return {"message": "LeadScraper AI - Agency Edition API is running"}

@app.get("/refine-query")
async def refine_query(requirement: str, category: str = "Direct Clients"):
    """
    Uses Gemini to refine the search query based on agency requirements, 
    targeting specific business segments and high-value regions.
    """
    if not GEMINI_API_KEY:
        return {"query": requirement}
        
    prompt = f"""
    You are an expert lead generation strategist for a Marketing & Development Agency.
    The goal is to find high-potential leads for the following target category: {category}.
    
    User Input: "{requirement}"
    
    Agency Target Strategy:
    1. Direct Clients: Local businesses (shops, hotels, clinics, etc.) needing websites/SEO.
    2. Partners/Startups: Small agencies or startups that can outsource development work.
    3. Freelancer Network: Individual professionals or hubs that can provide leads or collaborate.
    
    Special Instruction: Optimize the query for countries with high-value currencies (USA, UK, Canada, UAE, Singapore, etc.) unless a specific location is provided.
    
    Tasks:
    1. Create the most effective single search query string for Google Maps/Local results.
    2. Focus on "buying intent" or "collaboration intent".
    3. Return ONLY the search query string, nothing else.
    """
    try:
        response = model.generate_content(prompt)
        refined_query = response.text.strip().replace('"', '')
        return {"query": refined_query}
    except Exception as e:
        return {"query": requirement, "error": str(e)}

@app.get("/search")
async def search_leads(q: str, location: Optional[str] = None, engine: str = "serpapi"):
    try:
        leads = []
        
        if engine == "serpapi":
            params = {
                "engine": "google_maps",
                "q": q,
                "api_key": SERP_API_KEY,
                "type": "search"
            }
            if location:
                params["location"] = location

            response = requests.get("https://serpapi.com/search", params=params)
            data = response.json()

            if "error" in data:
                raise HTTPException(status_code=400, detail=data["error"])

            local_results = data.get("local_results", [])
            for result in local_results:
                leads.append({
                    "title": result.get("title"),
                    "address": result.get("address"),
                    "phone": result.get("phone"),
                    "website": result.get("website"),
                    "rating": result.get("rating"),
                    "reviews": result.get("reviews"),
                    "type": result.get("type"),
                    "place_id": result.get("place_id")
                })
        elif engine == "ddgs":
            try:
                from ddgs import DDGS
            except ImportError:
                raise HTTPException(status_code=500, detail="DuckDuckGo scraper (ddgs) not installed.")
            
            search_query = f"{q} {location}" if location else q
            results = DDGS().text(search_query, max_results=25)
            
            for res in results:
                leads.append({
                    "title": res.get("title", ""),
                    "address": res.get("body", "")[:120] + "...",  # Using description as a stand-in for address
                    "phone": None,
                    "website": res.get("href", ""),
                    "rating": None,
                    "reviews": None,
                    "type": "Organic Lead",
                    "place_id": res.get("href", "")
                })

        return {"leads": leads, "total": len(leads)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export")
async def export_to_sheets(leads: List[dict], spreadsheet_id: str, credentials_path: Optional[str] = "credentials.json"):
    if not os.path.exists(credentials_path):
        return {"error": "Google Sheets credentials not found. Please upload credentials.json."}

    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        client = gspread.authorize(creds)
        
        sh = client.open_by_key(spreadsheet_id)
        worksheet = sh.get_worksheet(0)

        header = ["Title", "Address", "Phone", "Website", "Rating", "Reviews", "Type"]
        rows = [header]
        for lead in leads:
            rows.append([
                lead.get("title", ""),
                lead.get("address", ""),
                lead.get("phone", ""),
                lead.get("website", ""),
                lead.get("rating", ""),
                lead.get("reviews", ""),
                lead.get("type", "")
            ])

        worksheet.clear()
        worksheet.update("A1", rows)

        return {"message": "Exported successfully", "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# For Vercel deployment
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
