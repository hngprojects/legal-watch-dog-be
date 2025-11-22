from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project


async def get_project_prompt(db: AsyncSession, project_id: str) -> Optional[str]:
    """
    Fetch the project's master_prompt.
    """
    statement = select(Project).where(Project.id == project_id)
    result = await db.execute(statement)
    project = result.scalar_one_or_none()

    if not project or not project.master_prompt:
        return None

    return project.master_prompt


async def get_jurisdiction_prompt(db: AsyncSession, jurisdiction_id: str) -> Optional[str]:
    """
    Fetch the jurisdiction's master_prompt.
    """
    statement = select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
    result = await db.execute(statement)
    jurisdiction = result.scalar_one_or_none()

    if not jurisdiction or not jurisdiction.master_prompt:
        return None

    return jurisdiction.master_prompt


async def build_final_prompt(
    db: AsyncSession,
    project_id: str,
    jurisdiction_id: Optional[str] = None,
) -> str:
    """
    Combine project + jurisdiction prompt.

    Logic:
    - Always include project prompt
    - If jurisdiction prompt exists, append it
    - If neither exists, return a safe fallback message
    """

    project_prompt = await get_project_prompt(db, project_id)
    jurisdiction_prompt = None

    if jurisdiction_id:
        jurisdiction_prompt = await get_jurisdiction_prompt(db, jurisdiction_id)

    if not project_prompt and not jurisdiction_prompt:
        return "No prompt has been configured for this project or jurisdiction."

    if project_prompt and not jurisdiction_prompt:
        return project_prompt

    if jurisdiction_prompt and not project_prompt:
        return jurisdiction_prompt

    final_prompt = (
        f"PROJECT INSTRUCTIONS:\n{project_prompt}\n\n"
        f"JURISDICTION-SPECIFIC INSTRUCTIONS:\n{jurisdiction_prompt}"
    )

    return final_prompt

