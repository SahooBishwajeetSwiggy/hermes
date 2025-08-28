from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import standalone
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

# Include routers
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_html():
    with open("static/index.html") as f:
        content = f.read()
        content = content.replace("GOOGLE_MAPS_API_KEY", MAPS_API_KEY)
        return content

app.include_router(standalone.router, prefix="/api/v1/routing", tags=["routing"])

@app.get("/")
async def health_check():
    return {"message": "Route Planner API is running"}
