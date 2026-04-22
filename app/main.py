from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse

from app.config import settings
from app.routers import export_router, health_router, leads_router, search_router

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.search_store = {}
    Path(settings.export_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(leads_router)
app.include_router(export_router)
app.include_router(health_router)


@app.get("/")
async def homepage(request: Request):
    # Serve the static HTML template file directly
    template_path = BASE_DIR / "templates" / "index.html"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(html_content)
    except FileNotFoundError:
        # Fallback to simple HTML if template file is not found
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>Lead Intel</title></head>
        <body>
            <h1>Lead Intel - Template Not Found</h1>
            <p>The template file could not be found. Using fallback page.</p>
            <a href="/docs">API Documentation</a>
        </body>
        </html>
        """)


@app.get("/admin")
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request, "settings": settings})


@app.get("/admin/settings")
async def get_admin_settings():
    """Return non-sensitive settings info for admin panel."""
    return {
        "search_api_provider": settings.search_api_provider,
        "has_search_api_key": bool(settings.search_api_key),
        "has_serp_api_key": bool(settings.serp_api_key),
        "has_gemini_api_key": bool(settings.gemini_api_key),
        "has_openai_api_key": bool(settings.openai_api_key),
        "has_app_secret": bool(settings.app_secret),
    }


@app.post("/admin/update")
async def update_credentials(
    request: Request,
    search_api_provider: str = Form(...),
    search_api_key: str = Form(""),
    serp_api_key: str = Form(""),
    gemini_api_key: str = Form(...),
    openai_api_key: str = Form(""),
    app_secret: str = Form(...),
):
    # Update settings in memory
    settings.search_api_provider = search_api_provider
    settings.search_api_key = search_api_key or None
    settings.serp_api_key = serp_api_key or None
    settings.gemini_api_key = gemini_api_key
    settings.openai_api_key = openai_api_key or None
    settings.app_secret = app_secret

    # Write to .env file
    env_path = Path(".env")
    env_lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            env_lines = f.readlines()
    
    # Update or add lines
    updates = {
        "SEARCH_API_PROVIDER": search_api_provider,
        "SEARCH_API_KEY": search_api_key,
        "SERP_API_KEY": serp_api_key,
        "GEMINI_API_KEY": gemini_api_key,
        "OPENAI_API_KEY": openai_api_key,
        "APP_SECRET": app_secret,
    }
    
    existing_keys = {line.split("=", 1)[0] for line in env_lines if "=" in line}
    for key, value in updates.items():
        if value:  # Only write if not empty
            if key in existing_keys:
                # Update existing
                for i, line in enumerate(env_lines):
                    if line.startswith(f"{key}="):
                        env_lines[i] = f"{key}={value}\n"
                        break
            else:
                # Add new
                env_lines.append(f"{key}={value}\n")
    
    with open(env_path, "w") as f:
        f.writelines(env_lines)
    
    return RedirectResponse(url="/admin", status_code=303)
