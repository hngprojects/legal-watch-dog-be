from typing import Dict, List

from pydantic import BaseModel


class ErrorResponseModel(BaseModel):
    error: str
    message: str
    status_code: int
    errors: Dict[str, List[str]]
