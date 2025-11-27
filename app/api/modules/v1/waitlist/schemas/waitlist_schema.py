from pydantic import BaseModel, EmailStr

<<<<<<< HEAD
=======

>>>>>>> fix/billing-model-cleanup
class WaitlistSignup(BaseModel):
    organization_email: EmailStr
    organization_name: str


class WaitlistResponse(BaseModel):
    organization_email: str
    organization_name: str
