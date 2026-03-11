"""
Dashboard Route - 首页/概览
"""

from fastapi import APIRouter, Request
from datetime import datetime, timedelta
from ..app import get_kb

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    """Dashboard 首页"""
    kb = get_kb()
    templates = request.app.state.templates

    # Get stats
    entity_count = len(kb.schema_mgr.entities)
    operation_count = len(kb.contract_exec.operations)
    agent_count = len(kb.policy_engine.agents)
    table_count = len(kb.db.list_tables())

    # Today's executions
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    audit_stats = kb.audit.get_statistics(since=today)
    today_exec = audit_stats.get("total", 0)

    stats = {
        "entities": entity_count,
        "operations": operation_count,
        "agents": agent_count,
        "tables": table_count,
        "today_executions": today_exec,
    }

    # Recent operations (last 10)
    recent_logs = kb.audit.query(limit=10)

    # DB file size
    db_size = 0
    db_path = kb.db.db_path
    if db_path and db_path.exists():
        db_size = db_path.stat().st_size

    if db_size < 1024:
        db_size_str = f"{db_size} B"
    elif db_size < 1024 * 1024:
        db_size_str = f"{db_size / 1024:.1f} KB"
    else:
        db_size_str = f"{db_size / (1024 * 1024):.1f} MB"

    system_status = {
        "db_size": db_size_str,
        "table_count": table_count,
        "schema_version": "1.0",
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_page": "dashboard",
            "stats": stats,
            "recent_logs": recent_logs,
            "system_status": system_status,
            "audit_stats": audit_stats,
        }
    )
