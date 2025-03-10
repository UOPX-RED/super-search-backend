from models import TextPayload, AnalysisResult, HighlightedSection
from langchain_aws import ChatBedrock
from uuid import uuid4
import json
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ai_service')


class TextAnalyzer:
    def __init__(self):
        logger.info("Initializing TextAnalyzer")
        # Default keywords if none provided
        self.default_keywords = [
            "diversity",
            "equity",
            "inclusion",
            "DEI",
            "underrepresented",
            "marginalized",
            "equality"
        ]

        # Initialize ChatBedrock for Claude v3
        logger.info("Setting up ChatBedrock with Claude v3")
        self.llm = ChatBedrock(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            model_kwargs={"max_tokens": 4000}
        )
        logger.info("TextAnalyzer initialization complete")

    def analyze_text(self, payload: TextPayload, request_id: str) -> AnalysisResult:
        logger.info(f"Starting analysis for request_id: {request_id}")
        # Use keywords from payload or fall back to defaults if empty
        keywords = payload.keywords if payload.keywords else self.default_keywords
        logger.info(f"Using keywords: {keywords}")

        # Construct the prompt
        prompt = self._build_prompt(payload.text, keywords)
        logger.debug(f"Generated prompt: {prompt[:100]}...")  # Log first 100 chars of prompt

        # Call the LLM
        logger.info("Calling LLM API")
        try:
            response = self.llm.invoke(prompt)
            logger.info("Received response from LLM API")
            logger.debug(f"LLM response: {response.content[:1000]}...")  # Log first 10 chars of response
        except Exception as e:
            logger.error(f"Error calling LLM API: {str(e)}", exc_info=True)
            raise

        # Parse the response
        logger.info("Parsing LLM response")
        result_data = self._parse_response(response.content)
        logger.info(f"Found {len(result_data.get('highlighted_sections', []))} highlighted sections")

        # Create analysis result
        logger.info("Creating analysis result")
        result = AnalysisResult(
            id=str(uuid4()),
            request_id=request_id,
            source_id=payload.source_id,
            content_type=payload.content_type,
            original_text=payload.text,
            keywords_searched=keywords,
            highlighted_sections=[HighlightedSection(**section) for section in
                                  result_data.get("highlighted_sections", [])],
            has_flags=len(result_data.get("highlighted_sections", [])) > 0,
            metadata=payload.metadata,
            keywords_matched=result_data.get("keywords_matched", [])
        )
        logger.info(f"Analysis complete for request_id: {request_id}, has_flags: {result.has_flags}")
        return result

    def _build_prompt(self, text, keywords):
        logger.info("Building prompt")
        # Building a concept-oriented prompt
        prompt = f"""Analyze the following educational text for content related to these concepts: {', '.join(keywords)}.
        
        I'm looking for semantic matches that relate to these concepts, not just exact keyword matches. For example, text discussing "creating opportunities for underserved populations" might be relevant to "equity" even if that exact word isn't used.
        
        For each relevant section you identify:
        1. Provide the start index, end index, and the matched text
        2. Explain WHY this section relates to one or more of the concepts (which concept and how it relates)
        3. Assign a confidence score (0.0-1.0) reflecting how strongly this relates to the concept
        
        YOU MUST RETURN YOUR RESPONSE AS A SINGLE VALID JSON OBJECT WITH THIS EXACT STRUCTURE:
        {{
        "highlighted_sections": [
            {{
            "start_index": <number>,
            "end_index": <number>,
            "matched_text": <string>,
            "reason": <string>,
            "concept_matched": <string>,
            "confidence": <number>
            }}
            
        ],
        "concepts_found": [<string>, <string>, ...] 
        }}
        
        If no concepts are found, return:
        {{
        "highlighted_sections": [],
        "concepts_found": []
        }}
        
        DO NOT include any explanations, comments, or additional text outside of the JSON structure. 
        YOUR ENTIRE RESPONSE MUST BE PARSEABLE AS JSON.
        
        Text to analyze:
        {text}"""

        return prompt

    def _parse_response(self, response_text):
        # Extract JSON from response
        logger.info("Parsing LLM response")
        try:
            # For chat models, extract the JSON part from the response
            json_str = response_text.strip()
            
          
            if "```json" in json_str:
                logger.info("Found JSON code block with ```json marker")
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                logger.info("Found JSON code block with ``` marker")
                parts = json_str.split("```")
                if len(parts) >= 3:  
                    json_str = parts[1].strip()
            
       
            try:
                result = json.loads(json_str)
                
            except json.JSONDecodeError:
                
                
                if json_str.find('{') != -1 and json_str.rfind('}') != -1:
                    start_idx = json_str.find('{')
                    end_idx = json_str.rfind('}') + 1
                    json_str = json_str[start_idx:end_idx]
                    result = json.loads(json_str)
                   
                else:
                    raise
            

            if "highlighted_sections" not in result:
                result["highlighted_sections"] = []
            if "keywords_matched" not in result and "concepts_found" in result:

                result["keywords_matched"] = result["concepts_found"]
            elif "keywords_matched" not in result:
                result["keywords_matched"] = []
                
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}", exc_info=True)
            # Fallback for parsing errors
            logger.warning("Using fallback empty result")
            return {"highlighted_sections": [], "keywords_matched": []}
