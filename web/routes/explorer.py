"""
Explorer Route - 数据浏览器
"""

import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from ..app import get_kb

router = APIRouter()


@router.get("/")
async def explorer_page(request: Request):
    """Explorer 主页"""
    kb = get_kb()
    templates = request.app.state.templates

    tables = kb.db.list_tables()
    operations = list(kb.contract_exec.operations.keys())

    # Get operation params for JS
    op_params = {}
    for op_name, op_def in kb.contract_exec.operations.items():
        op_params[op_name] = {
            pname: {
                "type": pdef.get("type", "string"),
                "required": pdef.get("required", False),
                "description": pdef.get("description", ""),
            }
            for pname, pdef in op_def.params.items()
        }

    return templates.TemplateResponse(
        "explorer.html",
        {
            "request": request,
            "active_page": "explorer",
            "tables": tables,
            "operations": operations,
            "op_params": op_params,
        }
    )


@router.get("/table/{table_name}")
async def table_data(request: Request, table_name: str, page: int = 1, per_page: int = 50):
    """Fetch table data (htmx partial)"""
    kb = get_kb()
    templates = request.app.state.templates

    # Sanitize table name
    tables = kb.db.list_tables()
    if table_name not in tables:
        return HTMLResponse(f'<div class="text-red-500 p-4">Table "{table_name}" not found</div>')

    offset = (page - 1) * per_page

    # Get total count
    count_result = kb.db.execute(f'SELECT COUNT(*) as cnt FROM "{table_name}"')
    total = count_result.rows[0][0] if count_result.rows else 0
    total_pages = max(1, (total + per_page - 1) // per_page)

    # Get data
    result = kb.db.execute(f'SELECT * FROM "{table_name}" LIMIT {per_page} OFFSET {offset}')
    columns = result.columns
    rows = [list(row) for row in result.rows]

    return templates.TemplateResponse(
        "partials/table_data.html",
        {
            "request": request,
            "table_name": table_name,
            "columns": columns,
            "rows": rows,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }
    )


@router.post("/query")
async def run_query(request: Request, sql: str = Form(...)):
    """Run a read-only SQL query"""
    kb = get_kb()
    templates = request.app.state.templates

    # Only allow SELECT and PRAGMA
    sql_clean = sql.strip().upper()
    if not (sql_clean.startswith("SELECT") or sql_clean.startswith("PRAGMA")):
        return templates.TemplateResponse(
            "partials/query_result.html",
            {
                "request": request,
                "error": "Only SELECT and PRAGMA queries are allowed",
                "sql": sql,
            }
        )

    try:
        result = kb.db.execute(sql)
        columns = result.columns
        rows = [list(row) for row in result.rows]
        return templates.TemplateResponse(
            "partials/query_result.html",
            {
                "request": request,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "sql": sql,
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/query_result.html",
            {
                "request": request,
                "error": str(e),
                "sql": sql,
            }
        )


@router.post("/execute")
async def execute_operation(request: Request):
    """Execute a contract operation"""
    kb = get_kb()
    templates = request.app.state.templates

    form = await request.form()
    op_name = form.get("operation")
    agent_id = form.get("agent_id", "webui_admin")
    agent_role = form.get("agent_role", "admin")

    if not op_name:
        return templates.TemplateResponse(
            "partials/execute_result.html",
            {"request": request, "error": "No operation selected"}
        )

    # Collect params
    params = {}
    for key, value in form.items():
        if key.startswith("param_") and value:
            param_name = key[6:]
            params[param_name] = value

    try:
        # Register a temporary agent if needed
        if not kb.policy_engine.is_registered(agent_id):
            kb.policy_engine.register_agent(
                agent_id=agent_id,
                role=agent_role,
                allowed_intents=list(kb.contract_exec.operations.keys()),
            )

        agent = kb.agent(agent_id, agent_role)
        result = agent.execute(op_name, params)

        return templates.TemplateResponse(
            "partials/execute_result.html",
            {
                "request": request,
                "success": result.success,
                "intent_name": result.intent_name,
                "result_data": result.result,
                "error": result.error,
                "risk_score": result.risk_score,
                "execution_ms": result.execution_ms,
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/execute_result.html",
            {"request": request, "error": str(e)}
        )
