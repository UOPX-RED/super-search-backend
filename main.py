# main.py
from fastapi import FastAPI, HTTPException
from models import TextPayload, AnalysisResult
from ai_service import TextAnalyzer
from db_service import DocumentDBService
from typing import List, Optional
from uuid import uuid4
from dotenv import load_dotenv
import logging
import os

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)