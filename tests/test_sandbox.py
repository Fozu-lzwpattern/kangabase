"""
Sandbox Tests
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kangabase.core.database import Database
from kangabase.core.sandbox import Sandbox


class TestSandbox:
    """Sandbox 测试"""
    
    @pytest.fixture
    def db(self):
        """Fixture: 创建临时数据库"""
        db = Database(":memory:")
        db.execute("CREATE TABLE test (id TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO test (id, value) VALUES (:id, :v)", {"id": "1", "v": "hello"})
        yield db
        db.close()
    
    @pytest.fixture
    def sandbox(self, db):
        """Fixture: 创建沙箱"""
        return Sandbox(db)
    
    def test_initialize(self, sandbox):
        """测试初始化"""
        sandbox.initialize()
        
        assert sandbox._initialized is True
    
    def test_dry_run(self, sandbox):
        """测试试运行"""
        sandbox.initialize()
        
        result = sandbox.dry_run("SELECT 1 as a")
        
        assert result["valid"] is True
        assert result["error"] is None
    
    def test_dry_run_invalid_sql(self, sandbox):
        """测试无效 SQL"""
        sandbox.initialize()
        
        result = sandbox.dry_run("SELECT * FROM nonexistent_table")
        
        assert result["valid"] is False
        assert result["error"] is not None
    
    def test_simulate(self, sandbox):
        """测试模拟"""
        sandbox.initialize()
        
        result = sandbox.simulate([
            ("INSERT INTO test (id, value) VALUES (:id, :v)", {"id": "2", "v": "world"}),
            ("SELECT * FROM test", {}),
        ])
        
        assert result["success"] is True
    
    def test_reset(self, sandbox):
        """测试重置"""
        sandbox.initialize()
        sandbox.dry_run("INSERT INTO test (id, value) VALUES (:id, :v)", {"id": "2", "v": "test"})
        
        sandbox.reset()
        
        assert sandbox._initialized is False
    
    def test_session(self, sandbox):
        """测试会话上下文"""
        sandbox.initialize()
        
        with sandbox.session() as db:
            result = db.execute("SELECT 1")
            assert result is not None
    
    def test_close(self, sandbox):
        """测试关闭"""
        sandbox.initialize()
        sandbox.close()
