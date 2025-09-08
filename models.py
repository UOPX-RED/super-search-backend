from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class TextPayload(BaseModel):
    source_id: str
    content_type: str = Field(..., description="Type of content (e.g., course, program, assignment)")
    text: str
    keywords: List[str] = Field(default_factory=list, description="Keywords or phrases to search for")
    metadata: Optional[Dict[str, Any]] = {}


class HighlightedSection(BaseModel):
    start_index: int
    end_index: int
    matched_text: str
    reason: str
    confidence: float


class AnalysisResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    source_id: str
    content_type: str
    original_text: str
    keywords_searched: List[str] = []
    highlighted_sections: List[HighlightedSection] = []
    has_flags: str = "false"
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    keywords_matched: List[str] = []

class AlternativeSuggestion(BaseModel):
    problematicPhrase: str
    alternatives: List[Union[str, Dict[str, Any]]]
    reason: str
    concept_matched: str
    confidence: float

class SuggestionPayload(BaseModel):
    source_id: str
    content_type: str = Field(..., description="Type of content (e.g., course, program, assignment)")
    sentence: str
    keywords: List[str] = Field(default_factory=list, description="Keywords or phrases to search for")
    metadata: Optional[Dict[str, Any]] = {}

class AlternateTextSuggestionResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    source_id: str
    content_type: str
    original_sentence: str
    keywords_searched: List[str] = []
    alternative_suggestions: List[AlternativeSuggestion] = []
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    message: str

def analyze_suggestions(payload: SuggestionPayload, request_id: str, text_content: str, keywords: List[str], result_data: Dict[str, Any]) -> AlternateTextSuggestionResult:
        result = AlternateTextSuggestionResult(
            id=str(uuid4()),
            request_id=request_id,
            source_id=payload.source_id,
            content_type=payload.content_type,
            original_sentence=text_content,
            keywords_searched=keywords,
            alternative_suggestions=[AlternativeSuggestion(**section) for section in
                                 result_data.get("alternative_suggestions", [])],
            metadata={**payload.metadata},
            message=result_data.get("message", "")
        )
        return result

def analyze_full_text_suggestions(payload: Dict[str, Any], request_id: str, llm, text_to_process: str, keywords: List[str], custom_prompt: str = "", mode: str = "full_text") -> dict:
        """
        Process a full text suggestion request and return formatted results
        """
        import logging
        import json
        from datetime import datetime
        from uuid import uuid4

        logging.info(f"Processing full text suggestion request: {request_id}")

        keywords_str = ", ".join(keywords)

        if not custom_prompt:
            if mode == "full_text":
                custom_prompt = f"""
                You are an educational content improver. Please rewrite the following educational text to avoid using terms related to: {keywords_str}.

                IMPORTANT INSTRUCTIONS:
                1. Preserve the educational meaning and context
                2. Replace or rephrase sections containing these keywords
                3. Maintain the same tone, style and educational level
                4. Provide exactly 3 alternative versions of the full text
                5. Each alternative should be a complete rewrite of the entire text
                6. Format your response as a JSON array with 3 strings, each containing a complete alternative text

                Return ONLY a valid JSON array like this:
                [
                  "First complete alternative text...",
                  "Second complete alternative text...",
                  "Third complete alternative text..."
                ]

                Original text:
                {text_to_process}
                """
        else:
            if "{text_to_process}" in custom_prompt:
                custom_prompt = custom_prompt.replace("{text_to_process}", text_to_process)
            elif "Original text:" not in custom_prompt and text_to_process not in custom_prompt:
                custom_prompt += f"\n\nOriginal text:\n{text_to_process}"

            if "JSON" not in custom_prompt and "json" not in custom_prompt:
                custom_prompt += """

                Format your response as a JSON array with alternatives, like this:
                [
                  "First alternative text...",
                  "Second alternative text...",
                  "Third alternative text..."
                ]

                Return ONLY valid JSON without any explanation text outside the JSON structure.
                """

        logging.info(f"Final prompt to be sent to LLM: {custom_prompt[:200]}...")

        logging.info(f"Calling LLM for full text suggestions")
        try:
            response = llm.invoke(custom_prompt)
            response_text = response.content
            logging.info("Received response from LLM")
            logging.debug(f"Raw response (first 200 chars): {response_text[:200]}")
        except Exception as e:
            logging.error(f"Error calling LLM: {str(e)}", exc_info=True)
            raise e

        alternatives = []
        try:
            json_str = response_text.strip()

            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                parts = json_str.split("```")
                if len(parts) >= 3:
                    json_str = parts[1].strip()

            if not json_str.startswith('['):
                start_idx = json_str.find('[')
                end_idx = json_str.rfind(']') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = json_str[start_idx:end_idx]

            try:
                result = json.loads(json_str)

                if isinstance(result, list):
                    alternatives = result
                elif isinstance(result, dict) and "alternatives" in result:
                    alternatives = result["alternatives"]
                else:
                    logging.warning(f"Unexpected response structure from AI")
                    alternatives = [json_str]
            except json.JSONDecodeError:
                logging.warning("Failed to parse response as JSON, looking for text alternatives")
                text_parts = response_text.split("\n\n")
                for part in text_parts:
                    if (part.strip().startswith("1.") or
                        part.strip().startswith("Alternative 1:") or
                        part.strip().startswith("Version 1:")):
                        alternatives.append(part.strip())

                if not alternatives:
                    logging.warning("No structured alternatives found, using raw response")
                    alternatives = [response_text]
        except Exception as e:
            logging.error(f"Error parsing AI response: {str(e)}", exc_info=True)
            alternatives = [response_text]

        if not alternatives:
            alternatives = ["The AI was unable to generate a suitable alternative. Please try with different keywords or a more specific prompt."]

        result_data = {
            "alternative_suggestions": [{
                "problematicPhrase": "full text",
                "alternatives": [alt[:100] + "..." for alt in alternatives],
                "reason": f"Full text rewrite to avoid: {', '.join(keywords)}",
                "concept_matched": keywords[0] if keywords else "content",
                "confidence": 0.85
            }],
            "message": "Successfully generated full text alternatives"
        }

        from models import SuggestionPayload
        suggestion_payload = SuggestionPayload(
            source_id=payload.get("source_id", "highlighted-text"),
            content_type=payload.get("content_type", "text"),
            sentence=text_to_process[:500] + "...",
            keywords=keywords,
            metadata=payload.get("metadata", {})
        )

        result = analyze_suggestions(
            suggestion_payload,
            request_id,
            text_to_process[:500] + "...",
            keywords,
            result_data
        )

        api_response = {
            "original_text": payload.get("original_text", ""),
            "keywords": keywords,
            "alternatives": alternatives,
            "id": result.id,
            "request_id": request_id
        }

        return {
            "db_result": result,
            "api_response": api_response
        }