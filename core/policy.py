"""
Policy Module - 权限引擎

设计原则:
- Agent 身份 + 角色 = 权限
- allowed_intents 白名单机制
- denied_intents 黑名单机制
- 约束规则（参数级限制）
- 风险阈值分级
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class PolicyDecision(Enum):
    """权限决策"""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CONFIRMATION = "require_confirmation"


@dataclass
class PolicyResult:
    """权限检查结果"""
    decision: PolicyDecision
    reason: str = ""
    constraints: dict = field(default_factory=dict)


class PolicyError(Exception):
    """权限异常"""
    pass


class PolicyEngine:
    """
    权限引擎
    
    核心职责:
    1. 基于 Agent 身份判断操作权限
    2. 支持 allowed/denied intents 白黑名单
    3. 参数级约束（如 max_amount, max_daily_count）
    4. 风险评分阈值分级
    """
    
    def __init__(self):
        """初始化权限引擎"""
        self.agents: dict[str, dict] = {}  # agent_id -> agent config
        self.risk_thresholds: dict[str, float] = {
            "auto_execute": 0.3,
            "execute_with_log": 0.7,
            "require_confirmation": 0.9,
            "deny": 1.0,
        }
    
    def load(self, policy_path: Path) -> "PolicyEngine":
        """
        加载策略文件
        
        Args:
            policy_path: YAML 策略文件路径
            
        Returns:
            self (链式调用)
        """
        if not policy_path.exists():
            raise FileNotFoundError(f"Policy file not found: {policy_path}")
        
        with open(policy_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        
        # 加载 Agent 策略
        for agent_id, agent_config in raw.get("agents", {}).items():
            self.agents[agent_id] = agent_config
        
        # 加载风险阈值
        if "risk_thresholds" in raw:
            self.risk_thresholds.update(raw["risk_thresholds"])
        
        return self
    
    def check(self, agent_id: str, intent_name: str, 
              params: Optional[dict] = None, risk_score: float = 0.0) -> PolicyResult:
        """
        权限检查
        
        Args:
            agent_id: Agent 标识
            intent_name: 意图/操作名
            params: 操作参数
            risk_score: 风险评分 (0-1)
            
        Returns:
            PolicyResult
        """
        params = params or {}
        
        # 检查 Agent 是否已注册
        agent_config = self.agents.get(agent_id)
        if not agent_config:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Unknown agent: {agent_id}"
            )
        
        # 1. 黑名单检查
        denied = agent_config.get("denied_intents", [])
        if intent_name in denied:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Intent '{intent_name}' is denied for agent '{agent_id}'"
            )
        
        # 2. 白名单检查
        allowed = agent_config.get("allowed_intents", [])
        if allowed and intent_name not in allowed:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Intent '{intent_name}' is not allowed for agent '{agent_id}'"
            )
        
        # 3. 参数约束检查
        constraints = agent_config.get("constraints", {}).get(intent_name, {})
        constraint_check = self._check_constraints(params, constraints)
        if constraint_check:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=constraint_check,
                constraints=constraints,
            )
        
        # 4. 风险评分判断
        return self._evaluate_risk(risk_score, constraints)
    
    def _check_constraints(self, params: dict, constraints: dict) -> Optional[str]:
        """检查参数约束"""
        for key, limit in constraints.items():
            if key.startswith("max_") and key[4:] in params:
                param_name = key[4:]
                try:
                    value = float(params[param_name])
                    if value > limit:
                        return f"Parameter '{param_name}' ({value}) exceeds max ({limit})"
                except (ValueError, TypeError):
                    continue
            
            if key.startswith("min_") and key[4:] in params:
                param_name = key[4:]
                try:
                    value = float(params[param_name])
                    if value < limit:
                        return f"Parameter '{param_name}' ({value}) below min ({limit})"
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _evaluate_risk(self, risk_score: float, constraints: dict) -> PolicyResult:
        """根据风险评分决策"""
        if risk_score >= self.risk_thresholds.get("deny", 1.0):
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Risk score ({risk_score}) exceeds deny threshold",
            )
        
        if risk_score >= self.risk_thresholds.get("require_confirmation", 0.9):
            return PolicyResult(
                decision=PolicyDecision.REQUIRE_CONFIRMATION,
                reason=f"Risk score ({risk_score}) requires human confirmation",
                constraints=constraints,
            )
        
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="Allowed",
            constraints=constraints,
        )
    
    def register_agent(self, agent_id: str, role: str = "default",
                       allowed_intents: list[str] | None = None,
                       denied_intents: list[str] | None = None,
                       constraints: dict | None = None) -> None:
        """
        动态注册 Agent
        
        Args:
            agent_id: Agent 标识
            role: 角色
            allowed_intents: 白名单
            denied_intents: 黑名单
            constraints: 约束
        """
        self.agents[agent_id] = {
            "role": role,
            "allowed_intents": allowed_intents or [],
            "denied_intents": denied_intents or [],
            "constraints": constraints or {},
        }
    
    def is_registered(self, agent_id: str) -> bool:
        """检查 Agent 是否已注册"""
        return agent_id in self.agents
    
    def get_role(self, agent_id: str) -> Optional[str]:
        """获取 Agent 角色"""
        config = self.agents.get(agent_id)
        return config.get("role") if config else None
    
    def get_allowed_intents(self, agent_id: str) -> list[str]:
        """获取 Agent 允许的操作列表"""
        config = self.agents.get(agent_id)
        return config.get("allowed_intents", []) if config else []
