"""
Intent Tests
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kangabase.core.intent import IntentRegistry, IntentMatch


class TestIntentRegistry:
    """IntentRegistry 测试"""
    
    @pytest.fixture
    def registry(self):
        """Fixture: 创建 IntentRegistry"""
        return IntentRegistry()
    
    def test_register(self, registry):
        """测试注册"""
        registry.register("发券给{user_id}", "issue_coupon")
        
        assert "issue_coupon" in registry.list_operations()
        assert "发券给{user_id}" in registry._patterns
    
    def test_match(self, registry):
        """测试匹配"""
        registry.register("发券给{user_id}", "issue_coupon")
        registry.register("用券{coupon_id}", "use_coupon")
        
        match = registry.match("发券给user123")
        
        assert match is not None
        assert match.operation == "issue_coupon"
        assert match.params["user_id"] == "user123"
    
    def test_match_no_match(self, registry):
        """测试无匹配"""
        registry.register("发券给{user_id}", "issue_coupon")
        
        match = registry.match("查询优惠券")
        assert match is None
    
    def test_resolve(self, registry):
        """测试解析"""
        registry.register("发券", "issue_coupon")
        
        op = registry.resolve("发券")
        assert op == "issue_coupon"
    
    def test_is_allowed(self, registry):
        """测试白名单检查"""
        registry.register("发券", "issue_coupon")
        registry.register("查询", "query")
        
        assert registry.is_allowed("issue_coupon") is True
        assert registry.is_allowed("unknown") is False
    
    def test_get_patterns(self, registry):
        """测试获取模式"""
        registry.register("发券", "issue_coupon")
        registry.register("发优惠券", "issue_coupon")
        
        patterns = registry.get_patterns("issue_coupon")
        assert len(patterns) == 2
    
    def test_remove(self, registry):
        """测试移除"""
        registry.register("发券", "issue_coupon")
        
        result = registry.remove("issue_coupon")
        assert result is True
        assert registry.is_allowed("issue_coupon") is False
    
    def test_clear(self, registry):
        """测试清空"""
        registry.register("a", "op1")
        registry.register("b", "op2")
        
        registry.clear()
        
        assert len(registry.list_operations()) == 0
    
    def test_to_dict(self, registry):
        """测试导出"""
        registry.register("发券{user_id}", "issue_coupon")
        
        d = registry.to_dict()
        
        assert "issue_coupon" in d["whitelist"]
        assert len(d["mappings"]) == 1
        assert d["mappings"][0]["operation"] == "issue_coupon"
    
    def test_patterns_multiple_params(self, registry):
        """测试多参数模式"""
        registry.register("转账{from}到{to}金额{amount}", "transfer")
        
        match = registry.match("转账A到B金额100")
        
        assert match.operation == "transfer"
        assert match.params["from"] == "A"
        assert match.params["to"] == "B"
        assert match.params["amount"] == "100"
