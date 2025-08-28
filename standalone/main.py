from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import standalone

import httpx
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(
    title="Route Planner API",
    description="""
    Route Planner API provides a comprehensive solution for managing delivery routes and vehicle fleets.
    """,
    version="1.0.0",
    docs_url="/api/docs",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO : In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

@app.get("/api/maps-proxy/{path:path}")
async def proxy_maps_request(path: str, request: Request):
    base_url = "https://maps.googleapis.com/maps/api"
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    params = dict(request.query_params)
    params['key'] = api_key
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/{path}", params=params)
            return Response(
                content=response.content,
                media_type=response.headers.get('content-type'),
                status_code=response.status_code
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Include routers
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_html():
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read())

app.include_router(standalone.router, prefix="/api/v1/routing", tags=["routing"])

@app.get("/")
async def health_check():
    return {"message": "Route Planner API is running"}
