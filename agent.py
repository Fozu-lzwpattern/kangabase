"""
Agent Module - Agent 身份 + SDK 接口

设计原则:
- Agent 身份抽象
- 统一的执行接口
- 权限检查 + 审计集成
- 沙箱预执行支持
"""

from __future__ import annotations

import uuid
import time
from typing import Any, Optional
from dataclasses import dataclass, field

from .core.intent import IntentRegistry
from .core.contract import ContractExecutor
from .core.policy import PolicyEngine, PolicyDecision
from .core.audit import AuditLogger, AuditStatus
from .core.events import EventBus, Event
from .core.sandbox import Sandbox


@dataclass
class ExecutionContext:
    """执行上下文"""
    agent_id: str
    session_id: str
    role: str
    use_sandbox: bool = False
    dry_run: bool = False


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    intent_name: str
    params: dict
    result: Any
    error: str | None = None
    risk_score: float = 0.0
    sandbox_used: bool = False
    execution_ms: float = 0.0
    audit_id: str | None = None


class Agent:
    """
    Agent SDK
    
    提供给 Agent 的统一接口：
    - 执行操作（NL 或结构化）
    - 权限检查
    - 沙箱预执行
    - 审计记录
    """
    
    def __init__(self, agent_id: str, role: str,
                 intent_registry: IntentRegistry,
                 contract_exec: ContractExecutor,
                 policy_engine: PolicyEngine,
                 audit: AuditLogger,
                 events: EventBus,
                 sandbox: Sandbox,
                 session_id: str = ""):
        """
        初始化 Agent
        
        Args:
            agent_id: Agent ID
            role: 角色
            intent_registry: Intent 注册表
            contract_exec: 契约执行器
            policy_engine: 权限引擎
            audit: 审计日志
            events: 事件总线
            sandbox: 沙箱
            session_id: 会话 ID
        """
        self.agent_id = agent_id
        self.role = role
        self.intent_registry = intent_registry
        self.contract_exec = contract_exec
        self.policy_engine = policy_engine
        self.audit = audit
        self.events = events
        self.sandbox = sandbox
        self.session_id = session_id or str(uuid.uuid4())
        
        # 注册效果处理器
        self._register_effect_handlers()
    
    def _register_effect_handlers(self):
        """注册契约效果处理器"""
        for op_name in self.contract_exec.list_operations():
            operation = self.contract_exec.get_operation(op_name)
            if not operation:
                continue
            
            for effect in operation.effects:
                event_name = effect.get("event")
                if event_name:
                    # 注册事件处理器
                    pass  # 预留
    
    def execute(self, intent: str, params: dict = None,
                source: str = "structured",
                use_sandbox: bool = False,
                dry_run: bool = False) -> ExecutionResult:
        """
        执行意图
        
        Args:
            intent: 意图名或 NL 文本
            params: 参数（结构化意图时）
            source: 来源 (structured/nl/llm)
            use_sandbox: 是否使用沙箱
            dry_run: 是否仅试运行
            
        Returns:
            ExecutionResult
        """
        params = params or {}
        start_time = time.time()
        
        # 1. 解析意图（如果是 NL）
        intent_name = intent
        resolved_params = params
        
        if source != "structured":
            match = self.intent_registry.match(intent)
            if not match:
                return ExecutionResult(
                    success=False,
                    intent_name=intent,
                    params=params,
                    result=None,
                    error=f"Cannot resolve intent: {intent}",
                )
            intent_name = match.operation
            resolved_params = {**match.params, **params}
        
        # 2. 检查权限
        risk_score = self._calculate_risk(intent_name, resolved_params)
        policy_result = self.policy_engine.check(
            self.agent_id, intent_name, resolved_params, risk_score
        )
        
        if policy_result.decision == PolicyDecision.DENY:
            return ExecutionResult(
                success=False,
                intent_name=intent_name,
                params=resolved_params,
                result=None,
                error=policy_result.reason,
                risk_score=risk_score,
            )
        
        # 3. 需要人工确认
        if policy_result.decision == PolicyDecision.REQUIRE_CONFIRMATION:
            # 记录审计（待确认状态）
            audit_id = self.audit.log(
                agent_id=self.agent_id,
                intent_name=intent_name,
                intent_params=resolved_params,
                status=AuditStatus.DENIED,
                session_id=self.session_id,
                agent_role=self.role,
                intent_source=source,
                risk_score=risk_score,
                sandbox_used=use_sandbox,
                error_message=policy_result.reason,
            )
            
            return ExecutionResult(
                success=False,
                intent_name=intent_name,
                params=resolved_params,
                result=None,
                error=f"Requires confirmation: {policy_result.reason}",
                risk_score=risk_score,
                audit_id=audit_id,
            )
        
        # 4. 沙箱预执行
        if use_sandbox:
            verify_result = self.sandbox.verify_contract(
                self.contract_exec, intent_name, resolved_params
            )
            if not verify_result["can_execute"]:
                return ExecutionResult(
                    success=False,
                    intent_name=intent_name,
                    params=resolved_params,
                    result=None,
                    error=f"Sandbox verification failed: {verify_result['precond_errors'] + verify_result['sql_errors']}",
                    risk_score=risk_score,
                    sandbox_used=True,
                )
        
        # 5. 执行操作
        if dry_run:
            # 仅沙箱执行
            result = self.sandbox.dry_run(
                self.contract_exec.get_operation(intent_name).steps[0].sql,
                resolved_params
            )
            execution_ms = (time.time() - start_time) * 1000
            
            return ExecutionResult(
                success=result["valid"],
                intent_name=intent_name,
                params=resolved_params,
                result=result.get("result"),
                error=result.get("error"),
                risk_score=risk_score,
                sandbox_used=use_sandbox,
                execution_ms=execution_ms,
            )
        
        # 实际执行
        try:
            exec_result = self.contract_exec.execute(intent_name, resolved_params)
            execution_ms = (time.time() - start_time) * 1000
            
            success = exec_result.get("status") == "success"
            
            # 6. 记录审计
            audit_id = self.audit.log(
                agent_id=self.agent_id,
                intent_name=intent_name,
                intent_params=resolved_params,
                status=AuditStatus.SUCCESS if success else AuditStatus.FAILED,
                session_id=self.session_id,
                agent_role=self.role,
                intent_source=source,
                risk_score=risk_score,
                sandbox_used=use_sandbox,
                error_message=exec_result.get("error"),
                execution_ms=execution_ms,
            )
            
            return ExecutionResult(
                success=success,
                intent_name=intent_name,
                params=resolved_params,
                result=exec_result.get("data"),
                error=exec_result.get("error"),
                risk_score=risk_score,
                sandbox_used=use_sandbox,
                execution_ms=execution_ms,
                audit_id=audit_id,
            )
        
        except Exception as e:
            execution_ms = (time.time() - start_time) * 1000
            
            # 记录失败审计
            audit_id = self.audit.log(
                agent_id=self.agent_id,
                intent_name=intent_name,
                intent_params=resolved_params,
                status=AuditStatus.FAILED,
                session_id=self.session_id,
                agent_role=self.role,
                intent_source=source,
                risk_score=risk_score,
                sandbox_used=use_sandbox,
                error_message=str(e),
                execution_ms=execution_ms,
            )
            
            return ExecutionResult(
                success=False,
                intent_name=intent_name,
                params=resolved_params,
                result=None,
                error=str(e),
                risk_score=risk_score,
                sandbox_used=use_sandbox,
                execution_ms=execution_ms,
                audit_id=audit_id,
            )
    
    def query(self, intent: str, params: dict = None) -> ExecutionResult:
        """
        执行查询（只读操作）
        
        Args:
            intent: 意图名
            params: 参数
            
        Returns:
            ExecutionResult
        """
        return self.execute(intent, params, source="structured")
    
    def explain(self, intent: str, params: dict = None) -> dict:
        """
        解释执行计划（不实际执行）
        
        Args:
            intent: 意图名
            params: 参数
            
        Returns:
            执行计划说明
        """
        params = params or {}
        
        # 解析意图
        intent_name = intent
        resolved_params = params
        
        match = self.intent_registry.match(intent)
        if match:
            intent_name = match.operation
            resolved_params = {**match.params, **params}
        
        # 获取操作定义
        operation = self.contract_exec.get_operation(intent_name)
        if not operation:
            return {"error": f"Unknown intent: {intent_name}"}
        
        # 构建执行计划
        plan = {
            "intent": intent_name,
            "description": operation.description,
            "params": resolved_params,
            "risk_level": operation.risk_level,
            "read_only": operation.read_only,
            "steps": [],
        }
        
        # 步骤说明
        for i, step in enumerate(operation.steps):
            plan["steps"].append({
                "index": i,
                "sql": step.sql,
                "generate": step.generate,
            })
        
        # 预条件
        plan["preconditions"] = [
            {
                "sql": p.get("sql", ""),
                "error": p.get("error", ""),
            }
            for p in operation.preconditions
        ]
        
        # 效果
        plan["effects"] = [
            e.get("event", "")
            for e in operation.effects
        ]
        
        # 权限检查
        risk_score = self._calculate_risk(intent_name, resolved_params)
        plan["risk_score"] = risk_score
        
        policy_result = self.policy_engine.check(
            self.agent_id, intent_name, resolved_params, risk_score
        )
        plan["policy"] = {
            "decision": policy_result.decision.value,
            "reason": policy_result.reason,
        }
        
        return plan
    
    def _calculate_risk(self, intent_name: str, params: dict) -> float:
        """计算风险评分"""
        risk_level = self.contract_exec.get_risk_level(intent_name)
        
        # 基础风险
        base_scores = {
            "low": 0.1,
            "medium": 0.5,
            "high": 0.9,
        }
        score = base_scores.get(risk_level.value, 0.3)
        
        # 金额类参数增加风险
        amount_keys = ["amount", "budget", "price", "cost"]
        for key in amount_keys:
            if key in params:
                try:
                    amount = float(params[key])
                    if amount > 1000:
                        score += 0.2
                    elif amount > 100:
                        score += 0.1
                except (ValueError, TypeError):
                    pass
        
        return min(score, 1.0)
    
    def list_intents(self) -> list[dict]:
        """列出 Agent 可用的意图"""
        allowed = self.policy_engine.get_allowed_intents(self.agent_id)
        
        result = []
        for intent_name in allowed:
            operation = self.contract_exec.get_operation(intent_name)
            if operation:
                result.append({
                    "name": intent_name,
                    "description": operation.description,
                    "patterns": operation.intent_patterns,
                    "risk_level": operation.risk_level,
                    "read_only": operation.read_only,
                })
        
        return result
