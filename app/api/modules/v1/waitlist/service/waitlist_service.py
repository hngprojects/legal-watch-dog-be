from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.api.modules.v1.waitlist.models.waitlist_model import Waitlist
from app.api.modules.v1.waitlist.schemas.waitlist_schema import WaitlistResponse
from app.api.core.dependencies.send_mail import send_email



class WaitlistService:
    """Business logic for waitlist operations"""
    
    async def add_to_waitlist(
        self, 
        db: AsyncSession, 
        organization_email: str, 
        organization_name:str,
    ) -> WaitlistResponse:
        """
        Add an email to the waitlist.
        
        Handles:
        - Email validation
        - Duplicate checking
        - Database insertion
        - Email notification
        - Logging
        """
        organization_email = organization_email.lower().strip()
        organization_name = organization_name.strip()
        
        
        # Check if exists
        if await self._email_exists(db, organization_email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered on waitlist"
            )
        
        # Create entry
        new_entry = Waitlist(organization_email=organization_email, organization_name=organization_name)
        db.add(new_entry)
        await db.flush()

        
        
        # Log
        self._log_signup(organization_email)
        
        return WaitlistResponse(
            success=True,
            message="Successfully added to waitlist.",
            organization_email=organization_email,
            organization_name=organization_name
        )
    
    async def _email_exists(self, db: AsyncSession, email: str) -> bool:
        """Check if email already exists"""
        stmt = select(Waitlist).where(Waitlist.organization_email == email.lower())
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def _send_confirmation_email(self, email: str, name: str):
        """Send confirmation email (implement with your email service)"""
        try:
            context = {
                "organization_name": name,
                "organization_email": email
            }
            await send_email(context)
            print(f"Waitlist email sent successfully to {email}")
        except Exception as e:
            print(f"Error sending email to {email}: {str(e)}")

    
    def _log_signup(self, email: str):
        """Log the signup event"""
        print(f"New waitlist signup: {email}")
        



waitlist_service = WaitlistService()