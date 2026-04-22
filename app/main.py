import logging
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Optional
import traceback

import os
from fastapi import FastAPI, Form, Request, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers import export, search
from app.services.db_service import db_service
from app.services.auth_service import verify_password, get_password_hash, create_access_token
from app.services.dependencies import get_current_user, require_user
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

# Templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
    logger.error(f"Global Exception: {error_msg}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "traceback": error_msg}
    )

@app.on_event("startup")
async def startup_db_client():
    await db_service.connect()

@app.on_event("shutdown")
async def shutdown_db_client():
    await db_service.disconnect()



# --- Routes ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    response: Response,
    email: str = Form(...),
    password: str = Form(...)
):
    user = await db_service.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user["email"]})
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, path="/", samesite="lax", secure=False)
    return {"message": "Login successful"}

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, user = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def signup(
    response: Response,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    existing = await db_service.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_data = {
        "name": name,
        "email": email,
        "password_hash": get_password_hash(password),
        "search_api_key": None,
        "gemini_api_key": None,
        "openai_api_key": None
    }
    await db_service.create_user(user_data)
    
    access_token = create_access_token(data={"sub": email})
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, path="/", samesite="lax", secure=False)
    return {"message": "Signup successful"}

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token", path="/")
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user = Depends(get_current_user)):
    if not user:
        return templates.TemplateResponse("landing.html", {"request": request})
    return templates.TemplateResponse("index.html", {"request": request, "settings": settings, "user": user})

@app.get("/history", response_class=HTMLResponse)
async def history(request: Request, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("history.html", {"request": request, "settings": settings, "user": user})

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("admin.html", {"request": request, "settings": settings, "user": user})

@app.post("/admin/update")
async def update_credentials(
    request: Request,
    search_api_key: str = Form(""),
    gemini_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    user = Depends(require_user)
):
    update_data = {}
    if search_api_key:
        update_data["search_api_key"] = search_api_key
    if gemini_api_key:
        update_data["gemini_api_key"] = gemini_api_key
    if openai_api_key:
        update_data["openai_api_key"] = openai_api_key

    if update_data:
        await db_service.update_user(user["email"], update_data)
        # Update local user object for template
        user.update(update_data)

    return templates.TemplateResponse("admin.html", {
        "request": request, 
        "settings": settings,
        "user": user,
        "message": "Credentials updated successfully!"
    })

# API Routes - Include protected routers
app.include_router(search.router)
app.include_router(export.router)

@app.get("/health")
async def health():
    return {"status": "ok", "db": db_service.db is not None}

@app.get("/api/credits")
async def credits(user = Depends(require_user)):
    # Use user's specific key if available, otherwise fallback to global
    key = user.get("search_api_key") or settings.search_api_key
    return await get_account_info(override_key=key)