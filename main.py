# main.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from models import TextPayload, AnalysisResult
from controllers.ai_service import TextAnalyzer
from controllers.db_service import DynamoDBService
from typing import List, Optional
from uuid import uuid4
from dotenv import load_dotenv
import logging
import os

from utils.azure_sso import (
    auth_middleware,
    init_auth,
    login,
    get_user_info_from_token,
    get_token_from_request,
    azure_token_middleware,
    validate_token
)

load_dotenv()

app = FastAPI(title="Educational Text Analysis API")
text_analyzer = TextAnalyzer()
db_service = DynamoDBService()

# Configure logging based on environment setting
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPEN_PATHS = [
    "/",
    "/healthz",
    "/docs",
    "/openapi.json",
    "/auth/login",
    "/auth/init",
    "/redoc"
]


@app.middleware("http")
async def sso_middleware(request: Request, call_next):
    return await auth_middleware(request, call_next, OPEN_PATHS)

@app.post("/analyze", response_model=AnalysisResult)
async def analyze_text(payload: TextPayload):
    """
    Analyze educational text for specific keywords/phrases and highlight matches
    """
    # Generate unique request ID
    request_id = str(uuid4())

    # Perform analysis
    result = text_analyzer.analyze_text(payload, request_id)

    # Save to database
    db_service.save_result(result)

    return result


@app.get("/results/{source_id}", response_model=List[AnalysisResult])
async def get_results(source_id: str):
    """
    Get analysis results for a specific source ID
    """
    results = db_service.get_results_by_source_id(source_id)
    if not results:
        raise HTTPException(status_code=404, detail=f"No results found for source_id: {source_id}")
    return results


@app.get("/flagged", response_model=List[AnalysisResult])
async def get_flagged_results(limit: int = 100):
    """
    Get results that contain flagged content
    """
    return db_service.get_flagged_results(limit)


@app.get("/result/{request_id}", response_model=AnalysisResult)
async def get_result_by_request_id(request_id: str):
    """
    Get analysis result by unique request ID
    """
    result = db_service.get_result_by_request_id(request_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No result found for request_id: {request_id}")
    return result


@app.get("/auth/init")
async def auth_init():
    return await init_auth()


@app.post("/auth/login")
async def auth_login(request: Request):
    return await login(request)


@app.get("/api/me")
async def get_current_user(request: Request):
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    is_valid = (
        azure_token_middleware(token) if request.headers.get("X-Azure-Token")
        else validate_token(token)
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_info = get_user_info_from_token(token)
    if not user_info:
        raise HTTPException(status_code=500, detail="Failed to extract")

    return user_info


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)