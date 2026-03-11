"""
Contract Tests
"""

import pytest
import sys
import yaml
from pathlib import Path
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from kangabase.core.database import Database
from kangabase.core.contract import ContractExecutor, RiskLevel


class TestContractExecutor:
    """ContractExecutor 测试"""
    
    @pytest.fixture
    def db(self):
        """Fixture: 创建临时数据库"""
        db = Database(":memory:")
        # 创建测试表
        db.execute("""
            CREATE TABLE campaigns (
                id TEXT PRIMARY KEY,
                name TEXT,
                budget REAL,
                status TEXT
            )
        """)
        db.execute("""
            CREATE TABLE coupons (
                id TEXT PRIMARY KEY,
                amount REAL,
                min_order REAL,
                status TEXT,
                user_id TEXT,
                campaign_id TEXT,
                created_at TEXT
            )
        """)
        
        # 插入测试数据
        db.execute(
            "INSERT INTO campaigns (id, name, budget, status) VALUES (:id, :name, :budget, :status)",
            {"id": "camp_001", "name": "Test Campaign", "budget": 1000.0, "status": "active"}
        )
        
        yield db
        db.close()
    
    @pytest.fixture
    def contract_exec(self, db):
        """Fixture: 创建契约执行器"""
        return ContractExecutor(db)
    
    @pytest.fixture
    def sample_contract(self, tmp_path):
        """Fixture: 创建示例契约"""
        contract = {
            "version": "1.0",
            "namespace": "test",
            "operations": {
                "create_campaign": {
                    "description": "创建活动",
                    "intent_patterns": ["创建活动{name}"],
                    "params": {
                        "name": {"type": "string", "required": True},
                        "budget": {"type": "decimal", "required": True, "min": 0}
                    },
                    "steps": [
                        {"sql": "INSERT INTO campaigns (id, name, budget, status) VALUES (:id, :name, :budget, 'draft')",
                         "generate": {"id": "uuid"}}
                    ],
                    "effects": [{"event": "campaign_created", "data": {"campaign_id": ":id"}}],
                    "risk_level": "medium"
                },
                "issue_coupon": {
                    "description": "发放优惠券",
                    "intent_patterns": ["发券"],
                    "params": {
                        "user_id": {"type": "string", "required": True},
                        "amount": {"type": "decimal", "required": True, "max": 100},
                        "campaign_id": {"type": "string", "required": True}
                    },
                    "preconditions": [
                        {"sql": "SELECT budget FROM campaigns WHERE id = :campaign_id AND status = 'active'",
                         "check": "result.budget >= :amount",
                         "error": "预算不足或活动未激活"}
                    ],
                    "steps": [
                        {"sql": "INSERT INTO coupons (id, amount, status, user_id, campaign_id, created_at) VALUES (:id, :amount, 'issued', :user_id, :campaign_id, datetime('now'))",
                         "generate": {"id": "uuid"}},
                        {"sql": "UPDATE campaigns SET budget = budget - :amount WHERE id = :campaign_id"}
                    ],
                    "risk_level": "medium"
                },
                "query_coupons": {
                    "description": "查询优惠券",
                    "intent_patterns": ["查询"],
                    "params": {
                        "user_id": {"type": "string", "required": False}
                    },
                    "steps": [
                        {"sql": "SELECT * FROM coupons WHERE (:user_id IS NULL OR user_id = :user_id)"}
                    ],
                    "risk_level": "low",
                    "read_only": True
                }
            }
        }
        
        path = tmp_path / "contract.yaml"
        with open(path, "w") as f:
            yaml.dump(contract, f)
        
        return path
    
    def test_load_contract(self, contract_exec, sample_contract):
        """测试加载契约"""
        contract_exec.load_contract(sample_contract)
        
        assert "test" in contract_exec.contracts
        assert "create_campaign" in contract_exec.operations
        assert "issue_coupon" in contract_exec.operations
    
    def test_validate_params(self, contract_exec, sample_contract):
        """测试参数校验"""
        contract_exec.load_contract(sample_contract)
        
        # 必填参数缺失
        valid, error = contract_exec.validate_params("create_campaign", {})
        assert valid is False
        assert "required" in error
        
        # 类型错误
        valid, error = contract_exec.validate_params("issue_coupon", {
            "user_id": "user1",
            "amount": "not_a_number",
            "campaign_id": "camp_001"
        })
        assert valid is False
        
        # 超出范围
        valid, error = contract_exec.validate_params("issue_coupon", {
            "user_id": "user1",
            "amount": 200,  # 超过 max: 100
            "campaign_id": "camp_001"
        })
        assert valid is False
        assert "100" in error
        
        # 正确参数
        valid, error = contract_exec.validate_params("issue_coupon", {
            "user_id": "user1",
            "amount": 50,
            "campaign_id": "camp_001"
        })
        assert valid is True
    
    def test_check_preconditions(self, contract_exec, sample_contract):
        """测试预条件检查"""
        contract_exec.load_contract(sample_contract)
        
        # 通过预条件
        passed, error = contract_exec.check_preconditions("issue_coupon", {
            "user_id": "user1",
            "amount": 50,
            "campaign_id": "camp_001"
        })
        assert passed is True
        
        # 预算不足
        passed, error = contract_exec.check_preconditions("issue_coupon", {
            "user_id": "user1",
            "amount": 2000,
            "campaign_id": "camp_001"
        })
        assert passed is False
    
    def test_execute(self, contract_exec, sample_contract):
        """测试执行操作"""
        contract_exec.load_contract(sample_contract)
        
        result = contract_exec.execute("create_campaign", {
            "name": "New Campaign",
            "budget": 5000.0
        })
        
        assert result["status"] == "success"
        assert "id" in result["data"]
        
        # 验证数据插入
        coupons = contract_exec.db.execute("SELECT * FROM campaigns")
        assert len(coupons.rows) >= 1
    
    def test_execute_with_compensation(self, contract_exec, sample_contract):
        """测试补偿机制"""
        # 模拟一个会失败的操作
        # ... (略)
    
    def test_risk_level(self, contract_exec, sample_contract):
        """测试风险等级"""
        contract_exec.load_contract(sample_contract)
        
        assert contract_exec.get_risk_level("query_coupons") == RiskLevel.LOW
        assert contract_exec.get_risk_level("issue_coupon") == RiskLevel.MEDIUM
    
    def test_read_only(self, contract_exec, sample_contract):
        """测试只读操作"""
        contract_exec.load_contract(sample_contract)
        
        assert contract_exec.is_read_only("query_coupons") is True
        assert contract_exec.is_read_only("issue_coupon") is False
    
    def test_register_effect_handler(self, contract_exec, sample_contract):
        """测试注册效果处理器"""
        contract_exec.load_contract(sample_contract)
        
        received = []
        
        def handler(data):
            received.append(data)
        
        contract_exec.register_effect_handler("campaign_created", handler)
        
        # 执行操作触发事件
        contract_exec.execute("create_campaign", {
            "name": "Test",
            "budget": 100.0
        })
        
        # 检查处理器是否被调用
        # ... (需要事件发布实现)
