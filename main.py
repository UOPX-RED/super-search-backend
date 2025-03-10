# main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from models import TextPayload, AnalysisResult
from controllers.ai_service import TextAnalyzer
from controllers.db_service import DocumentDBService
from typing import List, Optional
from uuid import uuid4
from dotenv import load_dotenv
import logging
import os

from utils.jwt import token_middleware, azure_token_middleware

load_dotenv()

app = FastAPI(title="Educational Text Analysis API")
text_analyzer = TextAnalyzer()
db_service = DocumentDBService()

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

@app.middleware("http")
async def validate_token(request, call_next):
    try:
        ignored_paths = [
            "/auth/login",
            "/auth/init",
            "/auth/login",
            "/analyze" # ignore for testing rn
        ]

        if request.url.path in ignored_paths or request.method == "OPTIONS":
            return await call_next(request)
        azure_token = request.headers.get("X-Azure-Token")
        if azure_token:
            validated = azure_token_middleware(azure_token)
            if not validated:
                return JSONResponse(content={"message": "Unauthorized"}, status_code=401)
            return await call_next(request)
        token = request.headers.get("Authorization")
        if not token:
            return JSONResponse(content={"message": "Unauthorized"}, status_code=401)
        validated = token_middleware(token)
        if not validated:
            return JSONResponse(content={"message": "Unauthorized"}, status_code=401)
        response = await call_next(request)
        return response
    except KeyError:
        return JSONResponse(content={"message": "Unauthorized"}, status_code=401)


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
    # db_service.save_result(result)

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
async def init_auth():
    TENANT_ID_SSO = os.getenv("TENANT_ID_SSO")
    CLIENT_ID_SSO = os.getenv("CLIENT_ID_SSO")
    REDIRECT_URI = os.getenv("REDIRECT_URI")
    redirectURL = f"https://login.microsoftonline.com/{TENANT_ID_SSO}/oauth2/v2.0/authorize?session=false&failureRedirect=%2Ffailed-login&response_type=code%20id_token&redirect_uri={REDIRECT_URI}&client_id={CLIENT_ID_SSO}&scope=openid%20profile%20email%20offline_access&nonce=abcde&response_mode=form_post"
    return redirectURL


@app.post("/auth/login")
async def login(request):
    print('hello')
    form = await request.form()
    body = dict(form)
    id_token = body.get("id_token")
    print('check', id_token)
    frontend_url = os.getenv("FRONTEND_URL")
    return RedirectResponse(f"{frontend_url}?jwt={id_token}", status_code=302)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)