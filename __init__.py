"""
KangaBase - 轻如 SQLite、易如 Supabase、为 Agent 而生的数据库框架

核心设计:
- Intent Registry 是架构枢纽：同时承担意图路由和安全白名单
- 操作契约 = 安全机制：Agent 只能选择预定义操作+填参数，不直接生成 SQL
- 配置层用 YAML 文件，运行时数据层用 SQLite
"""

__version__ = "0.1.0"

from typing import Optional
from pathlib import Path

from .core.database import Database
from .core.schema import SchemaManager
from .core.contract import ContractExecutor
from .core.intent import IntentRegistry
from .core.policy import PolicyEngine
from .core.audit import AuditLogger
from .core.events import EventBus
from .core.sandbox import Sandbox
from .agent import Agent


class KangaBase:
    """
    KangaBase 主入口类
    
    用法:
        kb = KangaBase("./data")
        kb.load_schema("schemas/coupon.yaml")
        kb.load_contract("contracts/coupon_ops.yaml")
        
        # Agent 操作
        agent = kb.agent("enterprise_agent", role="asB")
        result = agent.execute("issue_coupon", {
            "user_id": "user123",
            "amount": 10.0,
            "min_order": 50.0,
            "campaign_id": "camp001"
        })
    """
    
    def __init__(self, data_dir: str | Path = "./data"):
        """
        初始化 KangaBase
        
        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 核心组件
        self.db = Database(self.data_dir / "kangabase.db")
        self.schema_mgr = SchemaManager(self.db)
        self.contract_exec = ContractExecutor(self.db)
        self.intent_registry = IntentRegistry()
        self.policy_engine = PolicyEngine()
        self.audit = AuditLogger(self.db)
        self.events = EventBus()
        self.sandbox = Sandbox(self.db)
        
    def load_schema(self, schema_path: str | Path) -> "KangaBase":
        """加载 YAML Schema 并自动建表"""
        self.schema_mgr.load(Path(schema_path))
        self.schema_mgr.apply_all()
        return self
    
    def load_contract(self, contract_path: str | Path) -> "KangaBase":
        """加载操作契约"""
        self.contract_exec.load_contract(Path(contract_path))
        # 注册契约中的 intent
        for op_name, op_def in self.contract_exec.operations.items():
            patterns = op_def.intent_patterns if hasattr(op_def, 'intent_patterns') else []
            for pattern in patterns:
                self.intent_registry.register(pattern, op_name)
        return self
    
    def load_policy(self, policy_path: str | Path) -> "KangaBase":
        """加载权限策略"""
        self.policy_engine.load(Path(policy_path))
        return self
    
    def agent(self, agent_id: str, role: str = "default") -> Agent:
        """创建 Agent 实例"""
        return Agent(
            agent_id=agent_id,
            role=role,
            intent_registry=self.intent_registry,
            contract_exec=self.contract_exec,
            policy_engine=self.policy_engine,
            audit=self.audit,
            events=self.events,
            sandbox=self.sandbox,
        )
    
    def close(self):
        """关闭连接"""
        self.db.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def open(data_dir: str | Path = "./data") -> KangaBase:
    """
    打开 KangaBase 数据库
    
    用法:
        with KangaBase.open("./data") as kb:
            kb.load_schema("schemas/coupon.yaml")
            ...
    """
    return KangaBase(data_dir)
