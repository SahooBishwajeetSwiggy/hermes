from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import standalone

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

# Include routers
app.include_router(standalone.router, prefix="/api/v1/routing", tags=["routing"])

@app.get("/")
async def health_check():
    return {"message": "Route Planner API is running"}
