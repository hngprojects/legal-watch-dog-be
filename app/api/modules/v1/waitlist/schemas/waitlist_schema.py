from pydantic import BaseModel, EmailStr

class WaitlistSignup(BaseModel):
    organization_email: EmailStr
    organization_name: str


class WaitlistResponse(BaseModel):
    success: bool
    message: str
    organization_email: str
    organization_name: str