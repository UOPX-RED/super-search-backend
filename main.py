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
import httpx 
import time

from utils.get_api_token import (get_cognito_token,refresh_token,token_cache)
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

token = get_cognito_token()
print(f"Cognito Token: {token[:5]}")

# Automatically refresh the token if needed
if not token or token_cache['expiration'] <= time.time():
    print("Refreshing token...")
    token = refresh_token()
    print(f"Refreshed Cognito Token: {token[:5]}*****")

#get API URLs
COURSES_API_URL = os.getenv("COURSES_API_URL")
PROGRAMS_MS_URL = os.getenv("PROGRAMS_MS_URL")

app = FastAPI(title="Educational Text Analysis API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
text_analyzer = TextAnalyzer()
db_service = DynamoDBService()

# Configure logging based on environment setting
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


OPEN_PATHS = [
    "/",
    "/health",
    "/debug",
    "/docs",
    "/openapi.json",
    "/auth/login",
    "/auth/init",
    "/redoc",
    "/templates",
    "/course-details",
    "/programs",
    "/program-details", 
    "/analyze",
    "/keywordsearch",
    "/conceptsearch"
]


@app.middleware("http")
async def sso_middleware(request: Request, call_next):
    path = request.url.path
    logging.info(f"Request path: {path}")
    
    for open_path in OPEN_PATHS:
        if "{" in open_path:
            pattern = open_path.replace("{course_code:path}", ".*")
            import re
            if re.match(f"^{pattern}$", path):
                logging.info(f"Path {path} matches open path pattern {open_path}")
                break
        elif path == open_path or path.startswith(open_path + "/"):
            logging.info(f"Path {path} matches open path {open_path}")
            break
    else:
        logging.warning(f"Path {path} does not match any open path")
        
    return await auth_middleware(request, call_next, OPEN_PATHS)

@app.get("/health")
async def health_check():
    return {"status": "We up"}

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

@app.post("/keywordsearch", response_model=AnalysisResult)
async def analyze_text_by_keywords(payload: TextPayload):
    """
    Analyze educational text for specific keywords/phrases and highlight matches
    """
    # Generate unique request ID
    request_id = str(uuid4())

    # Perform analysis
    result = text_analyzer.analyze_text_lexical(payload, request_id)

    # Save to database
    db_service.save_result(result)

    return result

@app.post("/conceptsearch", response_model=AnalysisResult)
async def analyze_text_by_concept(payload: TextPayload):
    """
    Analyze educational text for specific keywords/phrases and highlight matches
    """
    # Generate unique request ID
    request_id = str(uuid4())

    # Perform analysis
    result = text_analyzer.analyze_text_semantic(payload, request_id)

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


@app.get("/templates")
async def get_templates():
    try:
        async with httpx.AsyncClient() as client:
            token = get_cognito_token()
            print(f"At getTemplates(), Cognito Token: {token[:5]}")
            # if not token:
            #     raise HTTPException(status_code=500, detail="API token not configured")
            if not token or token_cache['expiration'] <= time.time():
                print("Refreshing token...")
                token = refresh_token()
                print(f"Refreshed Cognito Token: {token[:5]}*****")
                
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            url = f"{COURSES_API_URL}/templates"

            response = await client.get(
                url,
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error from external API: {response.text}"
                )
                
            return response.json()
    except httpx.RequestError as e:
        logging.error(f"Error making request to external API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching templates: {str(e)}")


@app.get("/course-details")
async def get_course_details_query(courseCode: str):
    try:
        token = get_cognito_token()
        print(f"At get_course_details_query(), Cognito Token: {token[:5]}")

        # if not token:
        #     raise HTTPException(status_code=500, detail="API token not configured")
        if not token or token_cache['expiration'] <= time.time():
            print("Refreshing token...")
            token = refresh_token()
            print(f"Refreshed Cognito Token: {token[:5]}*****")
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        url = f"{COURSES_API_URL}/templates/curriculum?courseCode={courseCode}"
        print(f"URL: {url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error from external API: {response.text}"
                )
                
            return response.json()
    except httpx.RequestError as e:
        logging.error(f"Error making request to external API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching course details: {str(e)}")


@app.get("/programs")
async def get_programs():
    try:
        token = get_cognito_token()
        print(f"At get_programs(), Cognito Token: {token[:5]}")
        # if not token:
        #     raise HTTPException(status_code=500, detail="API token not configured")
        
        if not token or token_cache['expiration'] <= time.time():
            print("Refreshing token...")
            token = refresh_token()
            print(f"Refreshed Cognito Token: {token[:5]}*****")
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        logging.info(f"Making request to Programs MS with token: {token[:5]}...")
        
        async with httpx.AsyncClient() as client:
            url=f"{PROGRAMS_MS_URL}/programs/getAll"
            response = await client.get(url,
                headers=headers
            )
            
            logging.info(f"Programs MS response status: {response.status_code}")
            if response.status_code != 200:
                logging.error(f"PPrograms MS error response: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error from Programs MS: {response.text}"
                )
                
            return response.json()
    except httpx.RequestError as e:
        logging.error(f"Error making request to Programs MS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching programs: {str(e)}")

@app.get("/program-details")
async def get_programs_by_programId(programId: str):
    try:
        token = get_cognito_token()
        print(f"At get_programs_by_programId(), Cognito Token: {token[:5]}")
        # if not token:
        #     raise HTTPException(status_code=500, detail="API token not configured")
        
        # if not token.startswith("Bearer "):
        #     token = f"Bearer {token}"
        if not token or token_cache['expiration'] <= time.time():
            print("Refreshing token...")
            token = refresh_token()
            print(f"Refreshed Cognito Token: {token[:5]}*****")
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        logging.info(f"Making request to Programs MS with token: {token[:5]}...")
        
        async with httpx.AsyncClient() as client:
            url = f"{PROGRAMS_MS_URL}/templates?$filter=programId eq {programId}"
            response = await client.get(url,
                headers=headers
            )
            
            logging.info(f"Programs MS response status: {response.status_code}")
            if response.status_code != 200:
                logging.error(f"Programs MS error response: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error from Programs MS: {response.text}"
                )
                
            return response.json()
    except httpx.RequestError as e:
        logging.error(f"Error making request to Programs MS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching programs: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
