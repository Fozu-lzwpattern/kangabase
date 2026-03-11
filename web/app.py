"""
KangaBase WebUI - FastAPI Application

极简风格的管理后台，使用 Jinja2 + Tailwind CSS + htmx
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

# KangaBase imports
import sys
from pathlib import Path
# Ensure the parent directory (workspace) is in sys.path so 'kangabase' is importable
_workspace = Path(__file__).parent.parent.parent
if str(_workspace) not in sys.path:
    sys.path.insert(0, str(_workspace))

from kangabase import KangaBase

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Global KangaBase instance
_kb: Optional[KangaBase] = None


def get_kb() -> KangaBase:
    """Get the global KangaBase instance."""
    if _kb is None:
        raise RuntimeError("KangaBase not initialized. Call create_app() with proper config.")
    return _kb


def create_app(
    data_dir: str = "./data",
    schema_path: Optional[str] = None,
    contract_path: Optional[str] = None,
    policy_path: Optional[str] = None,
) -> FastAPI:
    """
    Create the FastAPI application.

    Args:
        data_dir: Path to data directory
        schema_path: Optional path to schema YAML
        contract_path: Optional path to contract YAML
        policy_path: Optional path to policy YAML
    """
    global _kb

    app = FastAPI(
        title="KangaBase WebUI",
        description="Agent-Native Database Management Console",
        version="0.1.0",
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Custom Jinja2 filters
    def tojson_filter(value):
        return json.dumps(value, ensure_ascii=False, default=str)

    templates.env.filters["tojson"] = tojson_filter

    # Store templates on app for route access
    app.state.templates = templates

    # Initialize KangaBase
    _kb = KangaBase(data_dir)

    if schema_path and Path(schema_path).exists():
        _kb.load_schema(schema_path)
        _kb.schema_mgr.apply_all()

    if contract_path and Path(contract_path).exists():
        _kb.load_contract(contract_path)

    if policy_path and Path(policy_path).exists():
        _kb.load_policy(policy_path)

    # Store config for settings page
    app.state.config = {
        "data_dir": str(Path(data_dir).resolve()),
        "schema_path": schema_path,
        "contract_path": contract_path,
        "policy_path": policy_path,
    }

    # Store kb instance in app.state for convenience
    app.state._kb = _kb

    # Register routes
    from .routes.dashboard import router as dashboard_router
    from .routes.schemas import router as schemas_router
    from .routes.contracts import router as contracts_router
    from .routes.explorer import router as explorer_router
    from .routes.audit import router as audit_router
    from .routes.agents import router as agents_router
    from .routes.settings import router as settings_router

    app.include_router(dashboard_router)
    app.include_router(schemas_router, prefix="/schemas")
    app.include_router(contracts_router, prefix="/contracts")
    app.include_router(explorer_router, prefix="/explorer")
    app.include_router(audit_router, prefix="/audit")
    app.include_router(agents_router, prefix="/agents")
    app.include_router(settings_router, prefix="/settings")

    return app
