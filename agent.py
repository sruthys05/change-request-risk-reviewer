"""The AI part. It has NO database access: it takes text in, gives a RiskSummary out."""
import os

from dotenv import load_dotenv
from pydantic import ValidationError

from models import RiskSummary

load_dotenv()

PROMPT = """You are an infrastructure change-risk reviewer.
Review this change request and reply with ONLY JSON, no other text:
{{"risk": "low" | "medium" | "high", "reasons": ["..."], "recommendation": "..."}}

Title: {title}
Description: {description}"""


def call_llm(prompt: str) -> str:
    """Talks to Anthropic. Tests replace this function with a fake."""
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env
    reply = client.messages.create(
        model=os.getenv("MODEL", "claude-sonnet-5-5"),
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return reply.content[0].text


def clean(text: str) -> str:
    """Remove ```json fences if the model added them."""
    text = text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```")
    return text.strip()


def review(title: str, description: str) -> RiskSummary:
    """Ask the LLM, validate the answer, retry once if it is bad."""
    error = None
    for _ in range(2):
        raw = call_llm(PROMPT.format(title=title, description=description))
        try:
            return RiskSummary.model_validate_json(clean(raw))
        except ValidationError as e:
            error = e
    raise ValueError(f"LLM gave invalid JSON twice: {error}")
