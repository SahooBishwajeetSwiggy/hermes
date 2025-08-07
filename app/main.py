from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.api.routes import warehouses, vehicles, configs

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
app.include_router(warehouses.router, prefix="/api/v1/warehouses", tags=["warehouses"])
app.include_router(vehicles.router, prefix="/api/v1/vehicles", tags=["vehicles"])
app.include_router(configs.router, prefix="/api/v1/configs", tags=["configs"])

@app.get("/")
async def health_check():
    return {"message": "Route Planner API is running"}
