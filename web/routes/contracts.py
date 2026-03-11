"""
Contracts Route - 操作契约
"""

from fastapi import APIRouter, Request
from ..app import get_kb

router = APIRouter()


@router.get("/")
async def contracts_list(request: Request):
    """Contracts 列表页"""
    kb = get_kb()
    templates = request.app.state.templates

    operations = {}
    for op_name, op_def in kb.contract_exec.operations.items():
        operations[op_name] = {
            "name": op_def.name,
            "description": op_def.description,
            "intent_patterns": op_def.intent_patterns,
            "risk_level": op_def.risk_level,
            "read_only": op_def.read_only,
            "params": {
                pname: {
                    "required": pdef.get("required", False),
                    "type": pdef.get("type", "string"),
                    "description": pdef.get("description", ""),
                    "min": pdef.get("min"),
                    "max": pdef.get("max"),
                }
                for pname, pdef in op_def.params.items()
            },
            "preconditions": [
                {
                    "sql": p.get("sql", ""),
                    "check": p.get("check", ""),
                    "error": p.get("error", ""),
                }
                for p in op_def.preconditions
            ],
            "steps": [
                {
                    "sql": step.sql,
                    "generate": step.generate,
                    "condition": step.condition,
                }
                for step in op_def.steps
            ],
            "effects": op_def.effects,
            "compensation": op_def.compensation,
        }

    return templates.TemplateResponse(
        "contracts.html",
        {
            "request": request,
            "active_page": "contracts",
            "operations": operations,
        }
    )
