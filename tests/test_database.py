"""
Database Tests
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kangabase.core.database import Database, QueryResult


class TestDatabase:
    """Database 测试"""
    
    @pytest.fixture
    def db(self):
        """Fixture: 创建临时数据库"""
        db = Database(":memory:")
        yield db
        db.close()
    
    def test_init(self, db):
        """测试初始化"""
        assert db is not None
    
    def test_execute(self, db):
        """测试执行 SQL"""
        result = db.execute("SELECT 1 as a, 2 as b")
        assert result.columns == ["a", "b"]
        assert tuple(result.rows[0]) == (1, 2)
        assert len(result.rows) == 1
    
    def test_execute_with_params(self, db):
        """测试参数化查询"""
        db.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        db.execute("INSERT INTO test (id, name) VALUES (:id, :name)", {"id": 1, "name": "test"})
        
        result = db.execute("SELECT * FROM test WHERE id = :id", {"id": 1})
        assert tuple(result.rows[0]) == (1, "test")
    
    def test_transaction(self, db):
        """测试事务"""
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        
        with db.transaction():
            db.execute("INSERT INTO test (value) VALUES (:v)", {"v": "a"})
            db.execute("INSERT INTO test (value) VALUES (:v)", {"v": "b"})
        
        result = db.execute("SELECT COUNT(*) FROM test")
        assert result.rows[0][0] == 2
    
    def test_transaction_rollback(self, db):
        """测试事务回滚"""
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        
        try:
            with db.transaction():
                db.execute("INSERT INTO test (value) VALUES (:v)", {"v": "a"})
                raise Exception("force rollback")
        except:
            pass
        
        result = db.execute("SELECT COUNT(*) FROM test")
        assert result.rows[0][0] == 0
    
    def test_table_exists(self, db):
        """测试表存在检查"""
        db.execute("CREATE TABLE test_table (id INTEGER)")
        assert db.table_exists("test_table") is True
        assert db.table_exists("nonexistent") is False
    
    def test_list_tables(self, db):
        """测试列出表"""
        db.execute("CREATE TABLE a (id INTEGER)")
        db.execute("CREATE TABLE b (id INTEGER)")
        
        tables = db.list_tables()
        assert "a" in tables
        assert "b" in tables
    
    def test_query_result_as_dicts(self, db):
        """测试结果转换为字典"""
        result = db.execute("SELECT 1 as id, 'test' as name")
        dicts = result.as_dicts()
        
        assert dicts == [{"id": 1, "name": "test"}]
    
    def test_query_result_first(self, db):
        """测试获取第一行"""
        result = db.execute("SELECT 1 as id UNION SELECT 2")
        first = result.first()
        
        assert first == {"id": 1}


class TestStorageAdapter:
    """StorageAdapter 测试"""
    
    @pytest.fixture
    def db_with_data(self):
        """Fixture: 创建带数据的数据库"""
        db = Database(":memory:")
        db.execute("""
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER
            )
        """)
        db.execute("INSERT INTO users (id, name, age) VALUES (:id, :name, :age)",
                   {"id": "1", "name": "Alice", "age": 30})
        db.execute("INSERT INTO users (id, name, age) VALUES (:id, :name, :age)",
                   {"id": "2", "name": "Bob", "age": 25})
        
        yield db
        db.close()
    
    def test_read(self, db_with_data):
        """测试读取"""
        from kangabase.core.database import StorageAdapter
        
        adapter = StorageAdapter(db_with_data)
        users = adapter.read("users")
        
        assert len(users) == 2
        assert users[0]["name"] == "Alice"
    
    def test_write(self, db_with_data):
        """测试写入"""
        from kangabase.core.database import StorageAdapter
        
        adapter = StorageAdapter(db_with_data)
        adapter.write("users", {"id": "3", "name": "Charlie", "age": 35})
        
        users = adapter.read("users")
        assert len(users) == 3
    
    def test_update(self, db_with_data):
        """测试更新"""
        from kangabase.core.database import StorageAdapter
        
        adapter = StorageAdapter(db_with_data)
        count = adapter.update("users", {"age": 31}, {"id": "1"})
        
        assert count == 1
        user = adapter.read("users", {"id": "1"})
        assert user[0]["age"] == 31
    
    def test_delete(self, db_with_data):
        """测试删除"""
        from kangabase.core.database import StorageAdapter
        
        adapter = StorageAdapter(db_with_data)
        count = adapter.delete("users", {"id": "1"})
        
        assert count == 1
        users = adapter.read("users")
        assert len(users) == 1
