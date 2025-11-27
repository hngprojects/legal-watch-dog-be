from pydantic import BaseModel

class StripeEvent(BaseModel):
    id: str
    type: str
    data: dict