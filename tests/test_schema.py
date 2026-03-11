"""
Schema Tests
"""

import pytest
import sys
import yaml
from pathlib import Path
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from kangabase.core.database import Database
from kangabase.core.schema import SchemaManager, FieldDef, EntityDef


class TestSchemaManager:
    """SchemaManager 测试"""
    
    @pytest.fixture
    def db(self):
        """Fixture: 创建临时数据库"""
        db = Database(":memory:")
        yield db
        db.close()
    
    @pytest.fixture
    def schema_mgr(self, db):
        """Fixture: 创建 SchemaManager"""
        return SchemaManager(db)
    
    @pytest.fixture
    def sample_schema(self, tmp_path):
        """Fixture: 创建示例 Schema 文件"""
        schema = {
            "version": "1.0",
            "namespace": "test",
            "entities": [
                {
                    "name": "User",
                    "description": "用户",
                    "storage": {"table": "users"},
                    "fields": {
                        "id": {"type": "string", "auto": "uuid"},
                        "name": {"type": "string", "description": "姓名", "required": True},
                        "age": {"type": "integer", "description": "年龄", "constraints": {"min": 0}},
                        "status": {"type": "enum", "values": ["active", "inactive"]},
                    }
                }
            ]
        }
        
        path = tmp_path / "schema.yaml"
        with open(path, "w") as f:
            yaml.dump(schema, f)
        
        return path
    
    def test_load_schema(self, schema_mgr, sample_schema):
        """测试加载 Schema"""
        schema_mgr.load(sample_schema)
        
        assert "test" in schema_mgr.schemas
        user = schema_mgr.get_entity("User")
        assert user is not None
        assert user.table == "users"
    
    def test_parse_field(self, schema_mgr):
        """测试字段解析"""
        field = schema_mgr._parse_field("name", {
            "type": "string",
            "description": "姓名",
            "required": True,
        })
        
        assert field.name == "name"
        assert field.type == "string"
        assert field.sql_type == "TEXT"
        assert field.description == "姓名"
        assert field.nullable is False
    
    def test_type_mapping(self, schema_mgr):
        """测试类型映射"""
        assert schema_mgr._parse_field("a", {"type": "string"}).sql_type == "TEXT"
        assert schema_mgr._parse_field("a", {"type": "integer"}).sql_type == "INTEGER"
        assert schema_mgr._parse_field("a", {"type": "decimal"}).sql_type == "REAL"
        assert schema_mgr._parse_field("a", {"type": "boolean"}).sql_type == "INTEGER"
    
    def test_synonym_index(self, schema_mgr):
        """测试同义词索引"""
        field = FieldDef(
            name="amount",
            type="decimal",
            sql_type="REAL",
            synonyms=["面额", "金额"]
        )
        
        entity = EntityDef(
            name="Coupon",
            description="优惠券",
            table="coupons",
            fields={"amount": field}
        )
        
        schema_mgr.entities["Coupon"] = entity
        schema_mgr._synonym_index["面额"] = "amount"
        schema_mgr._synonym_index["金额"] = "amount"
        
        assert schema_mgr.resolve_synonym("面额") == "amount"
        assert schema_mgr.resolve_synonym("金额") == "amount"
    
    def test_apply_entity(self, schema_mgr, db):
        """测试应用实体"""
        entity = EntityDef(
            name="User",
            description="用户",
            table="users",
            fields={
                "id": FieldDef("id", "string", "TEXT"),
                "name": FieldDef("name", "string", "TEXT"),
            }
        )
        
        schema_mgr.apply_entity(entity)
        
        assert db.table_exists("users")
    
    def test_validate_schema_missing_version(self):
        """测试校验缺少 version"""
        from kangabase.core.schema import SchemaValidationError
        
        mgr = SchemaManager(Database(":memory:"))
        
        with pytest.raises(SchemaValidationError, match="version"):
            mgr._validate_schema({"entities": []})
    
    def test_validate_schema_missing_entities(self):
        """测试校验缺少 entities"""
        from kangabase.core.schema import SchemaValidationError
        
        mgr = SchemaManager(Database(":memory:"))
        
        with pytest.raises(SchemaValidationError, match="entities"):
            mgr._validate_schema({"version": "1.0"})
    
    def test_generate_ddl(self, schema_mgr, sample_schema):
        """测试生成 DDL"""
        schema_mgr.load(sample_schema)
        
        ddl = schema_mgr.generate_ddl("User")
        
        assert "CREATE TABLE" in ddl
        assert "users" in ddl
        assert "id" in ddl
        assert "name" in ddl
    
    def test_to_dict(self, schema_mgr, sample_schema):
        """测试导出字典"""
        schema_mgr.load(sample_schema)
        
        d = schema_mgr.to_dict()
        
        assert "User" in d
        assert d["User"]["table"] == "users"
