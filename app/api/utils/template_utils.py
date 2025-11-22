from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_template(template_name: str, context: dict) -> str:
    """
    Render an email template with the given context.

    Args:
        template_name: Name of the template file (e.g., 'otp.html')
        context: Dictionary of variables to pass to the template

    Returns:
        Rendered HTML string
    """
    # Navigate from utils/ to core/dependencies/email/templates/
    template_dir = Path(__file__).parent.parent / "core" / "dependencies" / "email" / "templates"

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_name)
    return template.render(**context)
