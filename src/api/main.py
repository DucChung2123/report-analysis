from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from src.api.routes import router as api_router
from src.schemas.document import HealthResponse
from src.api.middleware import  logging_middleware, error_handler_middleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting application: PDF Processor API")
    print(f"API available at {API_PREFIX}")
    
    yield  
    
    print("Application shutdown")



app = FastAPI(
    title="ESG Financial Analyzer",
    description="API for analyzing ESG criteria in financial reports",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_middleware(request: Request, call_next):
    response = await logging_middleware(request, call_next)
    return response

API_PREFIX = "/api/v1"
app.include_router(api_router, prefix=API_PREFIX)


@app.get("/health", tags=["health"], response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="ok")