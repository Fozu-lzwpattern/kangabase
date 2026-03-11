"""
Policy Tests
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kangabase.core.policy import PolicyEngine, PolicyDecision


class TestPolicyEngine:
    """PolicyEngine 测试"""
    
    @pytest.fixture
    def engine(self):
        """Fixture: 创建 PolicyEngine"""
        return PolicyEngine()
    
    def test_register_agent(self, engine):
        """测试注册 Agent"""
        engine.register_agent(
            "test_agent",
            role="asB",
            allowed_intents=["issue_coupon", "query_coupons"],
            denied_intents=["use_coupon"]
        )
        
        assert engine.is_registered("test_agent")
        assert engine.get_role("test_agent") == "asB"
    
    def test_allow(self, engine):
        """测试允许"""
        engine.register_agent("test_agent", "asB", allowed_intents=["issue_coupon"])
        
        result = engine.check("test_agent", "issue_coupon")
        
        assert result.decision == PolicyDecision.ALLOW
    
    def test_deny_not_in_whitelist(self, engine):
        """测试不在白名单"""
        engine.register_agent("test_agent", "asB", allowed_intents=["query_coupons"])
        
        result = engine.check("test_agent", "issue_coupon")
        
        assert result.decision == PolicyDecision.DENY
    
    def test_deny_blacklist(self, engine):
        """测试黑名单"""
        engine.register_agent(
            "test_agent", 
            "asB", 
            allowed_intents=["issue_coupon"],
            denied_intents=["issue_coupon"]  # 同时在白名单和黑名单，黑名单优先
        )
        
        result = engine.check("test_agent", "issue_coupon")
        
        assert result.decision == PolicyDecision.DENY
    
    def test_constraints(self, engine):
        """测试约束"""
        engine.register_agent(
            "test_agent",
            "asB",
            allowed_intents=["issue_coupon"],
            constraints={"issue_coupon": {"max_amount": 50}}
        )
        
        # 超过约束
        result = engine.check("test_agent", "issue_coupon", {"amount": 100})
        assert result.decision == PolicyDecision.DENY
        assert "exceeds" in result.reason.lower()
        
        # 在约束内
        result = engine.check("test_agent", "issue_coupon", {"amount": 30})
        assert result.decision == PolicyDecision.ALLOW
    
    def test_risk_evaluation(self, engine):
        """测试风险评估"""
        engine.register_agent("test_agent", "asB", allowed_intents=["issue_coupon"])
        
        # 低风险
        result = engine.check("test_agent", "issue_coupon", {}, risk_score=0.1)
        assert result.decision == PolicyDecision.ALLOW
        
        # 高风险需要确认
        result = engine.check("test_agent", "issue_coupon", {}, risk_score=0.95)
        assert result.decision == PolicyDecision.REQUIRE_CONFIRMATION
        
        # 最高风险拒绝
        result = engine.check("test_agent", "issue_coupon", {}, risk_score=1.0)
        assert result.decision == PolicyDecision.DENY
    
    def test_unknown_agent(self, engine):
        """测试未知 Agent"""
        result = engine.check("unknown_agent", "issue_coupon")
        
        assert result.decision == PolicyDecision.DENY
    
    def test_get_allowed_intents(self, engine):
        """测试获取允许的意图列表"""
        engine.register_agent("test_agent", "asB", allowed_intents=["a", "b", "c"])
        
        allowed = engine.get_allowed_intents("test_agent")
        
        assert allowed == ["a", "b", "c"]
