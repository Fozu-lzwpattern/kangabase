"""
Audit Log Route - 审计日志
"""

import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
from ..app import get_kb

router = APIRouter()


@router.get("/")
async def audit_page(
    request: Request,
    agent_id: str = Query(None),
    intent_name: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50),
):
    """Audit Log 页面"""
    kb = get_kb()
    templates = request.app.state.templates

    # Get filter values
    agents = list(kb.policy_engine.agents.keys()) if kb.policy_engine.agents else []
    operations = list(kb.contract_exec.operations.keys())
    statuses = ["success", "failed", "denied", "sandbox"]

    # Build query filters
    filters = {}
    if agent_id:
        filters["agent_id"] = agent_id
    if intent_name:
        filters["intent_name"] = intent_name
    if status:
        filters["status"] = status
    filters["limit"] = limit

    # Query logs
    logs = kb.audit.query(**filters)

    # Get statistics
    stats = kb.audit.get_statistics(since=datetime.now() - timedelta(days=7))

    return templates.TemplateResponse(
        "audit.html",
        {
            "request": request,
            "active_page": "audit",
            "logs": logs,
            "agents": agents,
            "operations": operations,
            "statuses": statuses,
            "filters": filters,
            "stats": stats,
        }
    )


@router.get("/entry/{entry_id}")
async def audit_entry_detail(request: Request, entry_id: str):
    """Get audit entry detail (htmx partial)"""
    kb = get_kb()
    templates = request.app.state.templates

    # Get the entry from recent logs
    logs = kb.audit.query(limit=1000)
    entry = None
    for log in logs:
        if log.id == entry_id:
            entry = log
            break

    if not entry:
        return HTMLResponse(f'<div class="p-4 text-red-500">Entry not found</div>')

    return templates.TemplateResponse(
        "partials/audit_detail.html",
        {
            "request": request,
            "entry": entry,
        }
    )
