from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.api.core.config import BASE_DIR

TEMPLATE_DIR = Path(BASE_DIR) / "app/api/core/dependencies/email/templates"
email_templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
