"""
Agents Route - Agent管理
"""

from fastapi import APIRouter, Request
from ..app import get_kb

router = APIRouter()


@router.get("/")
async def agents_list(request: Request):
    """Agents 列表页"""
    kb = get_kb()
    templates = request.app.state.templates

    agents = {}
    for agent_id, agent_config in kb.policy_engine.agents.items():
        # Get allowed intents
        allowed = agent_config.get("allowed_intents", [])
        denied = agent_config.get("denied_intents", [])
        role = agent_config.get("role", "default")
        constraints = agent_config.get("constraints", {})

        # Get full operation details for allowed intents
        allowed_ops = []
        for op_name in allowed:
            op_def = kb.contract_exec.operations.get(op_name)
            if op_def:
                allowed_ops.append({
                    "name": op_name,
                    "description": op_def.description,
                    "risk_level": op_def.risk_level,
                    "read_only": op_def.read_only,
                    "constraints": constraints.get(op_name, {}),
                })

        agents[agent_id] = {
            "id": agent_id,
            "role": role,
            "allowed_count": len(allowed),
            "denied_count": len(denied),
            "allowed_operations": allowed_ops[:5],  # Show first 5
            "all_allowed": allowed,
            "denied_operations": denied,
            "constraints": constraints,
        }

    # Risk thresholds
    risk_thresholds = kb.policy_engine.risk_thresholds

    # All available operations
    all_operations = list(kb.contract_exec.operations.keys())

    return templates.TemplateResponse(
        "agents.html",
        {
            "request": request,
            "active_page": "agents",
            "agents": agents,
            "risk_thresholds": risk_thresholds,
            "all_operations": all_operations,
        }
    )
