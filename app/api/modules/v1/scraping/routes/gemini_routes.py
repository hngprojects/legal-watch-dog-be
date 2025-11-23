from fastapi import APIRouter
from pydantic import BaseModel

from app.api.modules.v1.scraping.service.gemini_client import GeminiClient

router = APIRouter()
gemini = GeminiClient()


class MessageRequest(BaseModel):
    message: str


@router.post("/ask/")
async def ask_gemini(req: MessageRequest):
    response_text = gemini.ask(req.message)
    return {"response": response_text}
