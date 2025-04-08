from models import TextPayload, AnalysisResult
from langchain_aws import ChatBedrock
from uuid import uuid4
import json
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ai_service_for_alternat_test_suggestion')

load_dotenv()

class StatementSuggester:

    def __init__(self,  request_id):
        
        self.request_id = request_id

        self.default_keywords = [
            "Anti-Racism", "Racism", "Race", "Allyship", "Bias", "DEI", 
            "Diversity", "Diverse", "Confirmation Bias", "Equity", "Equitableness", 
            "Feminism", "Gender", "Gender Identity",
            "Inclusion", "Inclusive", "All-Inclusive", "Inclusivity", "Injustice", "Intersectionality", "Prejudice", "Privilege", 
            "Racial Identity", "Sexuality", "Stereotypes", "Pronouns", "Transgender", "Equality Allyship",
        ]

        self.default_condition = f"Please rewrite the following sentence for a course that is teaching and assessing the following skills without using the following list of words  {', '.join(self.default_keywords)}"

        # Initialize ChatBedrock for Claude v3
        logger.info("Setting up ChatBedrock with Claude v3")
        self.llm = ChatBedrock(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            model_kwargs={"max_tokens": 4000},
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        logger.info("StatementSuggester initialization complete")

    def analyze_suggestions(self, payload: TextPayload, request_id: str) -> AnalysisResult:
        logger.info(f"Starting analysis for request_id: {request_id}")

        # Use keywords from payload or fall back to defaults if empty
        keywords = payload.keywords if payload.keywords else self.default_keywords
        logger.info(f"Using keywords: {keywords}")

        #skills = payload.skills if payload.keywords else ""

        # Construct the prompt
        prompt = self._build_prompt(payload.sentence, keywords, payload.req_prompt)
        # Log first 100 chars of prompt
        logger.debug(f"Generated prompt: {prompt[:100]}...")

        # Call the LLM
        logger.info("Calling LLM API")
        try:
            response = self.llm.invoke(prompt)
            logger.info("Received response from LLM API")
            # Log first 10 chars of response
            logger.debug(f"LLM response: {response.content[:1000]}...")
        except Exception as e:
            logger.error(f"Error calling LLM API: {str(e)}", exc_info=True)
            raise

        # Parse the response
        logger.info("Parsing LLM response")
        result_data = self._parse_response(response.content)
        logger.info(
            f"Found {len(result_data.get('highlighted_sections', []))} highlighted sections")

        # Create analysis result
        logger.info("Creating analysis result")
        result = AnalysisResult(
            id=str(uuid4()),
            request_id=request_id,
            source_id=payload.source_id,
            content_type=payload.content_type,
            original_sentence=payload.sentence,
            #keywords_searched=keywords,
            #highlighted_sections=[HighlightedSection(**section) for section in
            #                      result_data.get("highlighted_sections", [])],
            #has_flags='true' if len(result_data.get("highlighted_sections", [])) > 0 else 'false',
            metadata=payload.metadata,
            #keywords_matched=result_data.get("keywords_matched", [])
        )
        logger.info(
            f"Analysis complete for request_id: {request_id}, has_flags: {result.has_flags}")
        return result

    def _build_prompt(self, sentence, req_prompt):
        req_prompt = req_prompt if req_prompt else self.default_condition
        prompt = f"""
            {req_prompt}
            
            YOU MUST RETURN YOUR RESPONSE AS A SINGLE VALID JSON OBJECT WITH THIS EXACT STRUCTURE:
            {{
            "alternative_suggestions": [
                {{
                    "problematicPhrase": <string>
                    "alternatives": [<object<string>>, <object<string>>, ...],
                    "reason": <string>
                    "concept_matched": <string>,
                    "confidence": <number>
                }}    
            ]
            "message": "successfully generated suggestions"
            }}
            
            If no suggestions are found, return:
            {{
            "alternative_suggestions": [],
            "message": "Cannot suggest alternatives, please try another prompt"
            }}
            
            DO NOT include any explanations, comments, or additional text outside of the JSON structure. 
            YOUR ENTIRE RESPONSE MUST BE PARSEABLE AS JSON.

            Sentence to analyze:
            {sentence}"""
            

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
