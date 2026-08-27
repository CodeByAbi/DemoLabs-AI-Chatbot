"""
Azure OpenAI service for chat completions
"""
import logging
from typing import Optional, Dict, Any
from openai import AzureOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class AzureOpenAIChatService:
    """
    Service for chat completions using Azure OpenAI API.
    """
    
    def __init__(self):
        """Initialize Azure OpenAI client."""
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
        self.chat_deployment = settings.AZURE_OPENAI_CHAT_DEPLOYMENT
        self.chat_model = settings.AZURE_OPENAI_CHAT_MODEL
        logger.info(f"Initialized Azure OpenAI Chat Service with deployment: {self.chat_deployment}")
    
    def generate_chat_response(
        self, 
        system_prompt: str, 
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> tuple[Optional[str], Dict[str, int]]:
        """
        Generate a chat completion response.
        
        Args:
            system_prompt: System prompt defining bot behavior
            user_message: User's message
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            
        Returns:
            Tuple of (response_text, token_usage) where token_usage contains:
            - prompt_tokens: Input tokens
            - completion_tokens: Output tokens
            - total_tokens: Total tokens
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            response = self.client.chat.completions.create(
                model=self.chat_deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            reply = response.choices[0].message.content
            
            # Extract token usage from response
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0
            }
            
            logger.info(
                f"Generated chat response: {len(reply)} chars, "
                f"tokens: {token_usage['total_tokens']} "
                f"(input: {token_usage['prompt_tokens']}, output: {token_usage['completion_tokens']})"
            )
            
            return reply, token_usage
            
        except Exception as e:
            logger.error(f"Error generating chat response: {str(e)}", exc_info=True)
            return None, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    def generate_persona_preview(
        self,
        persona_name: str,
        persona_prompt: str,
        preview_question: str = "Hi, who are you?"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a preview response for a persona.
        
        Args:
            persona_name: Name of the persona
            persona_prompt: System prompt defining persona behavior
            preview_question: Question to ask (default: "Hi, who are you?")
            
        Returns:
            Dictionary with question and answer, or None if error
        """
        try:
            response, token_usage = self.generate_chat_response(
                system_prompt=persona_prompt,
                user_message=preview_question,
                temperature=0.7,
                max_tokens=300
            )
            
            if response:
                return {
                    "persona_name": persona_name,
                    "question": preview_question,
                    "answer": response,
                    "token_usage": token_usage
                }
            return None
            
        except Exception as e:
            logger.error(f"Error generating persona preview: {str(e)}", exc_info=True)
            return None


# Create global instance
azure_openai_chat_service = AzureOpenAIChatService()
