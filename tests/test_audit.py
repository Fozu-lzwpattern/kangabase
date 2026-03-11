"""
Audit Tests
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from kangabase.core.database import Database
from kangabase.core.audit import AuditLogger, AuditStatus


class TestAuditLogger:
    """AuditLogger 测试"""
    
    @pytest.fixture
    def db(self):
        """Fixture: 创建临时数据库"""
        db = Database(":memory:")
        yield db
        db.close()
    
    @pytest.fixture
    def audit(self, db):
        """Fixture: 创建审计日志"""
        return AuditLogger(db)
    
    def test_log(self, audit):
        """测试记录日志"""
        audit_id = audit.log(
            agent_id="agent1",
            intent_name="issue_coupon",
            intent_params={"user_id": "user1"},
            status=AuditStatus.SUCCESS,
            agent_role="asB",
        )
        
        assert audit_id is not None
        assert len(audit_id) > 0
    
    def test_query(self, audit):
        """测试查询日志"""
        # 插入几条记录
        audit.log("agent1", "issue_coupon", {}, AuditStatus.SUCCESS)
        audit.log("agent1", "query_coupons", {}, AuditStatus.SUCCESS)
        audit.log("agent2", "use_coupon", {}, AuditStatus.FAILED)
        
        # 查询全部
        entries = audit.query(limit=10)
        assert len(entries) == 3
        
        # 按 Agent 查询
        entries = audit.query(agent_id="agent1")
        assert len(entries) == 2
        
        # 按操作查询
        entries = audit.query(intent_name="use_coupon")
        assert len(entries) == 1
        
        # 按状态查询
        entries = audit.query(status="failed")
        assert len(entries) == 1
    
    def test_statistics(self, audit):
        """测试统计"""
        audit.log("agent1", "issue_coupon", {}, AuditStatus.SUCCESS)
        audit.log("agent1", "query_coupons", {}, AuditStatus.SUCCESS)
        audit.log("agent2", "use_coupon", {}, AuditStatus.FAILED)
        
        stats = audit.get_statistics()
        
        assert stats["total"] == 3
        assert stats["by_status"]["success"] == 2
        assert stats["by_status"]["failed"] == 1
        assert stats["by_agent"]["agent1"] == 2
        assert stats["by_agent"]["agent2"] == 1
    
    def test_clear(self, audit):
        """测试清理"""
        audit.log("agent1", "test", {}, AuditStatus.SUCCESS)
        
        # 清理 30 天前的（不应该删除刚创建的）
        deleted = audit.clear()
        
        entries = audit.query()
        assert len(entries) == 1  # 仍然存在
