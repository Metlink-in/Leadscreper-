import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers import export, search
from app.services.db_service import db_service
from app.services.serp_service import get_account_info

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Lead Intel API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Templates
templates = Jinja2Templates(directory="app/templates")

# Initialize app state
app.state.search_store = {}

@app.on_event("startup")
async def startup_db_client():
    await db_service.connect()

@app.on_event("shutdown")
async def shutdown_db_client():
    await db_service.disconnect()

# Routes
app.include_router(search.router)
app.include_router(export.router)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "settings": settings})

@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    return templates.TemplateResponse("history.html", {"request": request, "settings": settings})

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request, "settings": settings})

@app.post("/admin/update")
async def update_credentials(
    request: Request,
    search_api_provider: str = Form(...),
    search_api_key: str = Form(""),
    gemini_api_key: str = Form(...),
    openai_api_key: str = Form(""),
    app_secret: str = Form(...),
):
    # Update settings in memory (only if they aren't the masked value)
    settings.search_api_provider = search_api_provider
    if search_api_key != "********":
        settings.search_api_key = search_api_key or None
    
    if gemini_api_key != "********":
        settings.gemini_api_key = gemini_api_key
        
    if openai_api_key != "********":
        settings.openai_api_key = openai_api_key or None
        
    if app_secret != "********":
        settings.app_secret = app_secret

    # Write to .env file
    env_path = Path(".env")
    env_lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            env_lines = f.readlines()
    
    # Update or add lines
    updates = {
        "SEARCH_API_PROVIDER": settings.search_api_provider,
        "SEARCH_API_KEY": settings.search_api_key or "",
        "GEMINI_API_KEY": settings.gemini_api_key,
        "OPENAI_API_KEY": settings.openai_api_key or "",
        "APP_SECRET": settings.app_secret,
    }
    
    existing_keys = {line.split("=", 1)[0] for line in env_lines if "=" in line}
    for key, value in updates.items():
        found = False
        for i, line in enumerate(env_lines):
            if line.startswith(f"{key}="):
                env_lines[i] = f"{key}={value}\n"
                found = True
                break
        if not found:
            env_lines.append(f"{key}={value}\n")
    
    with open(env_path, "w") as f:
        f.writelines(env_lines)

    return templates.TemplateResponse("admin.html", {
        "request": request, 
        "settings": settings,
        "message": "Credentials updated successfully!"
    })

@app.get("/health")
async def health():
    return {"status": "ok", "db": db_service.db is not None}

@app.get("/api/credits")
async def credits():
    return await get_account_info()