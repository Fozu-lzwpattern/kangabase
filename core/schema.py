"""
Schema Module - YAML Schema 解析、校验、注册

设计原则:
- 配置层用 YAML，运行时数据层用 SQLite
- 类型映射明确，约束可声明
- 支持同义词和描述（NL 解析用）
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


# Python 类型 -> SQLite 类型映射
TYPE_MAPPING = {
    "string": "TEXT",
    "text": "TEXT",
    "integer": "INTEGER",
    "int": "INTEGER",
    "decimal": "REAL",
    "float": "REAL",
    "boolean": "INTEGER",  # SQLite 用 0/1
    "bool": "INTEGER",
    "datetime": "DATETIME",
    "date": "DATE",
    "enum": "TEXT",  # enum 存为文本
    "json": "TEXT",  # JSON 存为文本
}


@dataclass
class FieldDef:
    """字段定义"""
    name: str
    type: str
    sql_type: str
    description: str = ""
    auto: Optional[str] = None  # uuid, now, autoincrement
    constraints: dict = field(default_factory=dict)
    synonyms: list[str] = field(default_factory=list)
    enum_values: list[str] = field(default_factory=list)
    nullable: bool = True
    default: Any = None


@dataclass  
class EntityDef:
    """实体定义"""
    name: str
    description: str
    table: str
    fields: dict[str, FieldDef]
    primary_key: str = "id"


class SchemaValidationError(Exception):
    """Schema 校验异常"""
    pass


class SchemaManager:
    """
    Schema 管理器 - 解析 YAML Schema 并创建表
    
    用法:
        mgr = SchemaManager(db)
        mgr.load(Path("schemas/coupon.yaml"))
        mgr.apply_all()  # 创建所有表
    """
    
    def __init__(self, db):
        """
        初始化 Schema 管理器
        
        Args:
            db: Database 实例
        """
        self.db = db
        self.schemas: dict[str, dict] = {}  # namespace -> raw schema
        self.entities: dict[str, EntityDef] = {}  # entity_name -> EntityDef
        self._synonym_index: dict[str, str] = {}  # synonym -> field_name
    
    def load(self, schema_path: Path) -> "SchemaManager":
        """
        加载 YAML Schema 文件
        
        Args:
            schema_path: Schema 文件路径
            
        Returns:
            self (链式调用)
        """
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        
        self._validate_schema(raw)
        namespace = raw.get("namespace", "default")
        self.schemas[namespace] = raw
        
        # 解析实体
        for entity_raw in raw.get("entities", []):
            entity = self._parse_entity(entity_raw)
            self.entities[entity.name] = entity
            
            # 建立同义词索引
            for fname, fdef in entity.fields.items():
                for syn in fdef.synonyms:
                    self._synonym_index[syn] = fname
        
        return self
    
    def _validate_schema(self, raw: dict) -> None:
        """校验 Schema 格式"""
        if not isinstance(raw, dict):
            raise SchemaValidationError("Schema must be a dict")
        
        if "version" not in raw:
            raise SchemaValidationError("Schema missing 'version' field")
        
        if "entities" not in raw:
            raise SchemaValidationError("Schema missing 'entities' field")
        
        for idx, entity in enumerate(raw.get("entities", [])):
            if "name" not in entity:
                raise SchemaValidationError(f"Entity {idx} missing 'name'")
            if "fields" not in entity:
                raise SchemaValidationError(f"Entity '{entity.get('name')}' missing 'fields'")
    
    def _parse_entity(self, entity_raw: dict) -> EntityDef:
        """解析单个实体定义"""
        name = entity_raw["name"]
        storage = entity_raw.get("storage", {})
        table = storage.get("table", name.lower() + "s")
        
        fields = {}
        for fname, fraw in entity_raw.get("fields", {}).items():
            fields[fname] = self._parse_field(fname, fraw)
        
        return EntityDef(
            name=name,
            description=entity_raw.get("description", ""),
            table=table,
            fields=fields,
        )
    
    def _parse_field(self, name: str, raw: dict) -> FieldDef:
        """解析字段定义"""
        ftype = raw.get("type", "string")
        sql_type = TYPE_MAPPING.get(ftype, "TEXT")
        
        return FieldDef(
            name=name,
            type=ftype,
            sql_type=sql_type,
            description=raw.get("description", ""),
            auto=raw.get("auto"),
            constraints=raw.get("constraints", {}),
            synonyms=raw.get("synonyms", []),
            enum_values=raw.get("values", []),  # enum 类型
            nullable=not raw.get("required", False),
            default=raw.get("default"),
        )
    
    def get_entity(self, name: str) -> Optional[EntityDef]:
        """获取实体定义"""
        return self.entities.get(name)
    
    def get_table(self, entity_name: str) -> Optional[str]:
        """获取实体对应的表名"""
        entity = self.entities.get(entity_name)
        return entity.table if entity else None
    
    def resolve_synonym(self, word: str) -> Optional[str]:
        """解析同义词到字段名"""
        return self._synonym_index.get(word)
    
    def apply_all(self) -> None:
        """应用所有 Schema，创建表"""
        for entity in self.entities.values():
            self.apply_entity(entity)
    
    def apply_entity(self, entity: EntityDef) -> None:
        """
        应用单个实体的 Schema，创建表
        
        Args:
            entity: 实体定义
        """
        columns = {}
        for fname, fdef in entity.fields.items():
            col_def = fdef.sql_type
            
            # 处理约束
            if not fdef.nullable:
                col_def += " NOT NULL"
            if fdef.default is not None:
                if isinstance(fdef.default, str):
                    col_def += f" DEFAULT '{fdef.default}'"
                else:
                    col_def += f" DEFAULT {fdef.default}"
            
            columns[fname] = col_def
        
        # 主键处理
        pk = entity.primary_key
        if pk in columns:
            columns[pk] = columns[pk].replace(columns[pk].split()[0], "TEXT")
        else:
            columns[pk] = "TEXT"
        
        self.db.create_table(entity.table, columns, primary_key=pk)
    
    def generate_ddl(self, entity_name: str) -> str:
        """
        生成 DDL 语句
        
        Args:
            entity_name: 实体名
            
        Returns:
            CREATE TABLE SQL
        """
        entity = self.entities.get(entity_name)
        if not entity:
            raise ValueError(f"Entity not found: {entity_name}")
        
        cols = []
        for fname, fdef in entity.fields.items():
            col_def = f'"{fname}" {fdef.sql_type}'
            if not fdef.nullable:
                col_def += " NOT NULL"
            if fdef.default is not None:
                if isinstance(fdef.default, str):
                    col_def += f" DEFAULT '{fdef.default}'"
                else:
                    col_def += f" DEFAULT {fdef.default}"
            cols.append(col_def)
        
        cols.append(f'PRIMARY KEY ("{entity.primary_key}")')
        
        col_sep = ",\n  "
        return f"CREATE TABLE IF NOT EXISTS {entity.table} (\n  {col_sep.join(cols)}\n)"
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            name: {
                "description": e.description,
                "table": e.table,
                "fields": {
                    fn: {
                        "type": f.type,
                        "description": f.description,
                        "auto": f.auto,
                    }
                    for fn, f in e.fields.items()
                }
            }
            for name, e in self.entities.items()
        }
