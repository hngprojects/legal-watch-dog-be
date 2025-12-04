from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.modules.v1.projects.routes import project_routes as routes


def test_projects_router_has_billing_guard():
    """Ensure the projects router is configured with require_billing_access."""
    deps = routes.router.dependencies

    assert any(getattr(dep, "dependency", None) == require_billing_access for dep in deps), (
        "Projects router should include require_billing_access as a dependency"
    )
