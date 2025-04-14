from models import SuggestionPayload, AlternateTextSuggestionResult, AlternativeSuggestion, analyze_full_text_suggestions
from langchain_aws import ChatBedrock
from uuid import uuid4
import json
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level='INFO',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ai_service_for_alternat_test_suggestion')

load_dotenv()

class StatementSuggester:

    def __init__(self, request_id):
        
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

    def analyze_suggestions(self, payload, request_id: str) -> AlternateTextSuggestionResult:
        logger.info(f"Starting analysis for request_id: {request_id}")

        # Use keywords from payload or fall back to defaults if empty
        keywords = payload.keywords if payload.keywords else self.default_keywords
        logger.info(f"Using keywords: {keywords}")

        # Handle both text or sentence in payload
        text_content = ""
        if hasattr(payload, 'text'):
            text_content = payload.text
        elif hasattr(payload, 'sentence'):
            text_content = payload.sentence
        else:
            logger.error("Payload has neither 'text' nor 'sentence' attribute")
            text_content = ""

        # Handle req_prompt in both direct and metadata locations
        req_prompt_content = None
        if hasattr(payload, 'req_prompt'):
            req_prompt_content = payload.req_prompt
        elif hasattr(payload, 'metadata') and payload.metadata and 'req_prompt' in payload.metadata:
            req_prompt_content = payload.metadata['req_prompt']

        # Construct the prompt
        prompt = self._build_prompt(text_content, req_prompt_content)
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
        result = AlternateTextSuggestionResult(
            id=str(uuid4()),
            request_id=request_id,
            source_id=payload.source_id,
            content_type=payload.content_type,
            original_sentence=text_content,  # Use extracted text_content instead of payload.sentence
            keywords_searched=keywords,
            alternative_suggestions=[AlternativeSuggestion(**section) for section in
                                    result_data.get("alternative_suggestions", [])],
            metadata=payload.metadata,
            message=result_data.get("message", "")
        )
        logger.info(f"Analysis complete for request_id: {request_id}")
        return result

    def _build_prompt(self, text_content, req_prompt):
        if not text_content or len(text_content.strip()) < 5:
            text_content = "Students failed the assessment."

        keywords_to_avoid = ", ".join(self.default_keywords[:15]) if hasattr(self, 'default_keywords') else ""

        if not req_prompt:
            req_prompt = f"""Analyze this educational text and identify any phrases that could be improved to be more inclusive,
            especially those related to these concepts: {keywords_to_avoid}.

            When suggesting alternatives, DO NOT use any of these keywords in your alternatives: {keywords_to_avoid}.
            The alternatives must completely avoid these terms while preserving the educational meaning.

            Even if there are no obvious problematic terms, identify at least one phrase that could be expressed differently
            with more inclusive or student-centered language."""

        prompt = f"""
            You are an educational language specialist. {req_prompt}

            IMPORTANT INSTRUCTIONS:
            1. You MUST find at least one phrase to improve in the text, even if it's subtle.
            2. Your alternative suggestions must COMPLETELY AVOID using any of these terms: {keywords_to_avoid}
            3. Alternatives should maintain the same educational meaning but use more inclusive language.
            4. If nothing obvious is found, suggest improvements to general educational language or terminology.

            EXAMPLE:
            For the text "Students from diverse backgrounds apply accounting research tools", you might suggest:
            {{
                "problematicPhrase": "diverse backgrounds",
                "alternatives": [
                "various cultural contexts",
                "multiple cultural perspectives",
                "different cultural experiences"
                ],
                "reason": "The term 'diverse' can sometimes be used as a euphemism. Being specific about cultural differences is more inclusive.",
                "concept_matched": "diversity",
                "confidence": 0.85
            }}

            Notice that the alternatives COMPLETELY AVOID using the term "diverse" or "diversity".

            YOU MUST RETURN YOUR RESPONSE AS A SINGLE VALID JSON OBJECT WITH THIS EXACT STRUCTURE:
            {{
            "alternative_suggestions": [
                {{
                    "problematicPhrase": "<extract from text>",
                    "alternatives": ["<alternative 1>", "<alternative 2>", "<alternative 3>"],
                    "reason": "<explanation of why this change is recommended>",
                    "concept_matched": "<relevant concept or keyword>",
                    "confidence": <number between 0.5 and 1.0>
                }}
            ],
            "message": "successfully generated suggestions"
            }}

            IMPORTANT:
            - NEVER return empty alternative_suggestions
            - ALWAYS ensure your alternatives COMPLETELY AVOID using any of the problematic keywords
            - DO NOT include any explanations, comments, or additional text outside of the JSON structure
            - YOUR ENTIRE RESPONSE MUST BE PARSEABLE AS JSON

            Sentence to analyze:
            {text_content}
        """

        return prompt

    def _parse_response(self, response_text):
        # Extract JSON from response
        logger.info("Parsing LLM response")
        try:
            # For chat models, extract the JSON part from the response
            json_str = response_text.strip()

            logger.info(f"Raw response text: {json_str[:500]}...")

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

            # Process alternatives to ensure they match the expected format and don't contain problematic keywords
            if "alternative_suggestions" in result:
                for suggestion in result["alternative_suggestions"]:
                    if "alternatives" in suggestion and isinstance(suggestion["alternatives"], list):
                        cleaned_alternatives = []

                        for alt in suggestion["alternatives"]:
                            alt_text = alt if isinstance(alt, str) else alt.get("text", "")

                            contains_problematic = False
                            if hasattr(self, 'default_keywords'):
                                for keyword in self.default_keywords:
                                    if keyword.lower() in alt_text.lower():
                                        logger.warning(f"Alternative '{alt_text}' contains problematic keyword '{keyword}'")
                                        contains_problematic = True
                                        break

                            if not contains_problematic:
                                cleaned_alternatives.append({"text": alt_text} if isinstance(alt, str) else alt)

                        if not cleaned_alternatives:
                            logger.warning(f"All alternatives for '{suggestion.get('problematicPhrase', '')}' contained problematic keywords")
                            cleaned_alternatives = [{"text": "alternative wording needed - previous suggestions contained problematic terms"}]

                        suggestion["alternatives"] = cleaned_alternatives

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
            return {"highlighted_sections": [], "keywords_matched": [], "alternative_suggestions": []}
        except Exception as e:
            logger.error(f"Unexpected error in _parse_response: {str(e)}", exc_info=True)
            return {"highlighted_sections": [], "keywords_matched": [], "alternative_suggestions": []}

    def process_full_text_suggestion(self, request_data: dict, request_id: str = None):
        """
        Process a full text suggestion request
        """
        import os
        import logging
        from langchain_aws import ChatBedrock
        from models import analyze_full_text_suggestions

        if not request_id:
            from uuid import uuid4
            request_id = str(uuid4())

        original_text = request_data.get("original_text", "")
        keywords = request_data.get("keywords", [])
        custom_prompt = request_data.get("prompt", "")
        source_id = request_data.get("source_id", "highlighted-text")
        content_type = request_data.get("content_type", "text")
        metadata = request_data.get("metadata", {})
        mode = request_data.get("mode", "full_text")

        llm = ChatBedrock(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            model_kwargs={"max_tokens": 4000, "temperature": 0.7},
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )

        max_length = 10000
        text_to_process = original_text
        if len(original_text) > max_length:
            text_to_process = original_text[:max_length]
            last_para_break = text_to_process.rfind("\n\n")
            if last_para_break > max_length * 0.8:
                text_to_process = original_text[:last_para_break]

        payload = {
            "source_id": source_id,
            "content_type": content_type,
            "original_text": original_text,
            "metadata": metadata
        }

        try:
            result = analyze_full_text_suggestions(
                payload=payload,
                request_id=request_id,
                llm=llm,
                text_to_process=text_to_process,
                keywords=keywords,
                custom_prompt=custom_prompt,
                mode=mode
            )

            return result
        except Exception as e:
            logging.exception(f"Error in full text suggestion processing: {str(e)}")
            raise e