"""
Schemas Route - 实体浏览
"""

from fastapi import APIRouter, Request
from ..app import get_kb

router = APIRouter()


@router.get("/")
async def schemas_list(request: Request):
    """Schema 列表页"""
    kb = get_kb()
    templates = request.app.state.templates

    entities = {}
    for name, entity_def in kb.schema_mgr.entities.items():
        fields = {}
        for fname, fdef in entity_def.fields.items():
            fields[fname] = {
                "name": fdef.name,
                "type": fdef.type,
                "sql_type": fdef.sql_type,
                "description": fdef.description,
                "auto": fdef.auto,
                "constraints": fdef.constraints,
                "synonyms": fdef.synonyms,
                "enum_values": fdef.enum_values,
                "nullable": fdef.nullable,
                "default": fdef.default,
            }
        entities[name] = {
            "name": entity_def.name,
            "description": entity_def.description,
            "table": entity_def.table,
            "fields": fields,
            "primary_key": entity_def.primary_key,
            "field_count": len(fields),
        }

    # Get raw schema data for relationships, metrics, etc.
    raw_schemas = kb.schema_mgr.schemas

    # First entity selected by default
    selected = list(entities.keys())[0] if entities else None

    return templates.TemplateResponse(
        "schemas.html",
        {
            "request": request,
            "active_page": "schemas",
            "entities": entities,
            "selected": selected,
            "raw_schemas": raw_schemas,
        }
    )


@router.get("/detail/{entity_name}")
async def schema_detail(request: Request, entity_name: str):
    """Schema detail (htmx partial)"""
    kb = get_kb()
    templates = request.app.state.templates

    entity_def = kb.schema_mgr.entities.get(entity_name)
    if not entity_def:
        return templates.TemplateResponse(
            "partials/schema_detail.html",
            {"request": request, "entity": None, "error": f"Entity '{entity_name}' not found"}
        )

    fields = {}
    for fname, fdef in entity_def.fields.items():
        fields[fname] = {
            "name": fdef.name,
            "type": fdef.type,
            "sql_type": fdef.sql_type,
            "description": fdef.description,
            "auto": fdef.auto,
            "constraints": fdef.constraints,
            "synonyms": fdef.synonyms,
            "enum_values": fdef.enum_values,
            "nullable": fdef.nullable,
            "default": fdef.default,
        }

    entity = {
        "name": entity_def.name,
        "description": entity_def.description,
        "table": entity_def.table,
        "fields": fields,
        "primary_key": entity_def.primary_key,
    }

    # Generate DDL
    try:
        ddl = kb.schema_mgr.generate_ddl(entity_name)
    except Exception:
        ddl = ""

    return templates.TemplateResponse(
        "partials/schema_detail.html",
        {"request": request, "entity": entity, "ddl": ddl}
    )
