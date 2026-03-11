"""
Settings Route - 设置页面
"""

from pathlib import Path
from fastapi import APIRouter, Request
from ..app import get_kb

router = APIRouter()


@router.get("/")
async def settings_page(request: Request):
    """Settings 页面"""
    kb = get_kb()
    templates = request.app.state.templates
    config = request.app.state.config

    # Database info
    db_path = kb.db.db_path
    db_info = {
        "path": str(db_path) if db_path else ":memory:",
        "exists": db_path.exists() if db_path else False,
    }

    if db_path and db_path.exists():
        size = db_path.stat().st_size
        if size < 1024:
            db_info["size"] = f"{size} B"
        elif size < 1024 * 1024:
            db_info["size"] = f"{size / 1024:.1f} KB"
        else:
            db_info["size"] = f"{size / (1024 * 1024):.1f} MB"
    else:
        db_info["size"] = "N/A"

    # Tables
    tables = kb.db.list_tables()
    table_details = []
    for t in tables:
        try:
            count_result = kb.db.execute(f'SELECT COUNT(*) FROM "{t}"')
            count = count_result.rows[0][0] if count_result.rows else 0
            table_details.append({"name": t, "rows": count})
        except Exception:
            table_details.append({"name": t, "rows": "?"})

    # PRAGMA info
    pragmas = {}
    pragma_names = [
        "journal_mode", "wal_autocheckpoint", "synchronous",
        "foreign_keys", "page_size", "cache_size",
    ]
    for p in pragma_names:
        try:
            result = kb.db.execute(f"PRAGMA {p}")
            if result.rows:
                pragmas[p] = result.rows[0][0]
        except Exception:
            pragmas[p] = "N/A"

    # File paths
    file_paths = {
        "data_dir": config.get("data_dir", "N/A"),
        "schema_path": config.get("schema_path", "Not loaded"),
        "contract_path": config.get("contract_path", "Not loaded"),
        "policy_path": config.get("policy_path", "Not loaded"),
    }

    # Intent registry
    intent_info = kb.intent_registry.to_dict()

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "active_page": "settings",
            "db_info": db_info,
            "tables": table_details,
            "pragmas": pragmas,
            "file_paths": file_paths,
            "intent_info": intent_info,
        }
    )
