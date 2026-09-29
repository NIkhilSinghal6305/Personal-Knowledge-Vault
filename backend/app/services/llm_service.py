"""
LLM service using Google Gemini API.
Provides the core language model interaction for all AI features.
"""
import google.generativeai as genai
from typing import Optional
from app.config import get_settings

settings = get_settings()

# Configure Gemini
_model = None


def get_llm():
    """Get or create the Gemini model instance."""
    global _model
    if _model is None:
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please add it to your .env file. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


def generate_response(
    prompt: str,
    system_instruction: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """
    Generate a response from Gemini given a prompt.
    Uses a system instruction to set the AI's behavior.
    """
    try:
        model = get_llm()

        # Build the full prompt with system instruction
        full_prompt = ""
        if system_instruction:
            full_prompt = f"System Instruction: {system_instruction}\n\n"
        full_prompt += prompt

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response = model.generate_content(
            full_prompt,
            generation_config=generation_config,
        )

        if response and response.text:
            return response.text
        return "I was unable to generate a response. Please try again."

    except Exception as e:
        error_msg = str(e)
        if "API_KEY" in error_msg.upper() or "AUTHENTICATION" in error_msg.upper():
            return "Error: Invalid Gemini API key. Please check your .env configuration."
        if "QUOTA" in error_msg.upper() or "RATE" in error_msg.upper():
            return "Error: API rate limit reached. Please wait a moment and try again."
        return f"Error generating AI response: {error_msg}"
