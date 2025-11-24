import logging

from sqlalchemy import select

from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project

logger = logging.getLogger(__name__)


async def build_final_prompt(db, project_id: str, jurisdiction_id: str) -> str:
    """
    Build a generic LLM prompt by combining:
    - Project instructions (always included)
    - Jurisdiction instructions (if any, appended after project instructions)
    """
    logger.info(
        f"PromptService: Building LLM prompt for project_id={project_id}, "
        f"jurisdiction_id={jurisdiction_id}"
    )

    project_query = await db.execute(select(Project).where(Project.id == project_id))
    project = project_query.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project not found (id={project_id})")

    jurisdiction_query = await db.execute(
        select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
    )
    jurisdiction = jurisdiction_query.scalar_one_or_none()
    if not jurisdiction:
        raise ValueError(f"Jurisdiction not found (id={jurisdiction_id})")

    project_prompt = project.master_prompt or ""

    jurisdiction_prompt = jurisdiction.prompt or ""
    if project_prompt:
        if project_prompt:
            jurisdiction_prompt = (
                f"{project_prompt}\n{jurisdiction_prompt}"
                if jurisdiction_prompt
                else project_prompt
            )

    final_prompt = f"""
Instructions from project + jurisdiction:
{jurisdiction_prompt}

Use ONLY the scraped data that will be appended after this prompt to complete the task.
Follow instructions strictly.
"""

    logger.info("PromptService: Final LLM prompt successfully built.")
    return final_prompt.strip()