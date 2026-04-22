# Lead Intel

A production-ready FastAPI lead generation scraper for an AI/software development agency.

## Overview

This app scrapes client opportunities from search APIs (SearchApi.io or SerpAPI), enriches leads with Gemini AI, and surfaces them in a professional dark dashboard.

## Features

- Async FastAPI backend with startup/shutdown lifespan
- SearchApi.io / SerpAPI scraping for Google Search, Maps, and Jobs
- **Optimized search queries** with contact information extraction
- **Enhanced Gemini AI enrichment** with detailed lead analysis, contact extraction, and prioritization
- **Improved contact details extraction** using regex patterns and AI
- **Better lead presentation** with scoring, quality assessment, and priority ranking
- In-memory state with export support for CSV, JSON, and PDF
- Single-file Jinja2 dashboard with vanilla JavaScript
- Vercel-ready deployment via `vercel.json`

## Setup

1. Copy `.env.example` to `.env`.
2. Fill in your keys:
   - `SEARCH_API_PROVIDER` (optional, default: `searchapi`)
   - `SEARCH_API_KEY` or `SERP_API_KEY`
   - `GEMINI_API_KEY`
   - `APP_SECRET`
   - Optional: `OPENAI_API_KEY`
3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run locally

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

## Endpoints

- `GET /` — dashboard UI
- `POST /api/search` — triggers scraping and enrichment
- `GET /api/leads` — returns filtered lead data
- `GET /api/export/{format}` — exports `csv`, `json`, or `pdf`
- `GET /health` — service health check

## Deployment

This repo is ready for Vercel deployment.

1. Install the Vercel CLI.
2. Run:

```bash
vercel deploy --prod
```

The app is already configured to route all requests to `app/main.py`.

## Optimizations

### Search Query Optimization
- Enhanced search queries to specifically target contact information (email, phone)
- Improved location-based searches for better relevance
- Added platform-specific search patterns for Upwork, Freelancer, LinkedIn, etc.

### AI Enrichment Enhancements
- **Detailed Lead Analysis**: Gemini AI now provides comprehensive 2-3 sentence summaries
- **Contact Extraction**: AI-powered extraction of email and phone from descriptions
- **Lead Prioritization**: Added contact_priority (high/medium/low) and lead_quality ratings
- **Outreach Angles**: More personalized and compelling outreach suggestions

### Contact Details Extraction
- Regex-based extraction from lead descriptions and titles
- AI-powered contact information discovery
- Enhanced platform detection (added Glassdoor, AngelList support)

### Results Presentation
- Leads sorted by AI score (highest first)
- Summary statistics showing lead quality distribution
- Contact availability indicators
- Priority scoring for better lead management

## Notes

- All credentials load from `.env` via `pydantic-settings`
- Export files are saved temporarily under `./exports/`
- CORS is enabled for all origins for split frontend/backend deployments
