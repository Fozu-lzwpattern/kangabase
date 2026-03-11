"""
Contract Module - 操作契约执行器

设计原则:
- 操作契约 = 安全机制：Agent 只能选择预定义操作+填参数，不直接生成 SQL
- 预条件检查 + 步骤执行 + 效果发布 + 补偿机制
"""

from __future__ import annotations

import yaml
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContractError(Exception):
    """契约执行异常"""
    pass


class PreconditionError(ContractError):
    """预条件检查失败"""
    pass


@dataclass
class OperationStep:
    """操作步骤"""
    sql: str
    generate: dict[str, str] = field(default_factory=dict)  # {param: generator}
    condition: Optional[str] = None  # 条件执行


@dataclass
class OperationDef:
    """操作定义"""
    name: str
    description: str
    intent_patterns: list[str]
    params: dict  # 参数定义
    preconditions: list[dict]  # 预条件
    steps: list[OperationStep]  # 执行步骤
    effects: list[dict] = field(default_factory=list)  # 副作用
    compensation: list[dict] = field(default_factory=list)  # 补偿/回滚
    risk_level: str = "low"
    read_only: bool = False


class ContractExecutor:
    """
    操作契约执行器
    
    核心职责:
    1. 加载契约定义
    2. 解析和校验参数
    3. 执行预条件检查
    4. 执行操作步骤
    5. 发布效果事件
    6. 失败时执行补偿
    """
    
    def __init__(self, db):
        """
        初始化契约执行器
        
        Args:
            db: Database 实例
        """
        self.db = db
        self.contracts: dict[str, dict] = {}  # namespace -> raw contract
        self.operations: dict[str, OperationDef] = {}  # op_name -> OperationDef
        self._effect_handlers: dict[str, list[Callable]] = {}  # event -> handlers
    
    def load_contract(self, contract_path: Path) -> "ContractExecutor":
        """
        加载契约文件
        
        Args:
            contract_path: 契约 YAML 文件路径
            
        Returns:
            self (链式调用)
        """
        if not contract_path.exists():
            raise FileNotFoundError(f"Contract file not found: {contract_path}")
        
        with open(contract_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        
        self._validate_contract(raw)
        namespace = raw.get("namespace", "default")
        self.contracts[namespace] = raw
        
        # 解析操作
        for op_name, op_raw in raw.get("operations", {}).items():
            operation = self._parse_operation(op_name, op_raw)
            self.operations[op_name] = operation
        
        return self
    
    def _validate_contract(self, raw: dict) -> None:
        """校验契约格式"""
        if not isinstance(raw, dict):
            raise ContractError("Contract must be a dict")
        
        if "version" not in raw:
            raise ContractError("Contract missing 'version' field")
        
        if "operations" not in raw:
            raise ContractError("Contract missing 'operations' field")
    
    def _parse_operation(self, name: str, raw: dict) -> OperationDef:
        """解析操作定义"""
        steps = []
        for step_raw in raw.get("steps", []):
            steps.append(OperationStep(
                sql=step_raw.get("sql", ""),
                generate=step_raw.get("generate", {}),
                condition=step_raw.get("condition"),
            ))
        
        preconditions = raw.get("preconditions", [])
        
        return OperationDef(
            name=name,
            description=raw.get("description", ""),
            intent_patterns=raw.get("intent_patterns", []),
            params=raw.get("params", {}),
            preconditions=preconditions,
            steps=steps,
            effects=raw.get("effects", []),
            compensation=raw.get("compensation", []),
            risk_level=raw.get("risk_level", "low"),
            read_only=raw.get("read_only", False),
        )
    
    def get_operation(self, name: str) -> Optional[OperationDef]:
        """获取操作定义"""
        return self.operations.get(name)
    
    def list_operations(self) -> list[str]:
        """列出所有操作"""
        return list(self.operations.keys())
    
    def validate_params(self, op_name: str, params: dict) -> tuple[bool, str]:
        """
        校验参数
        
        Args:
            op_name: 操作名
            params: 参数字典
            
        Returns:
            (is_valid, error_message)
        """
        operation = self.operations.get(op_name)
        if not operation:
            return False, f"Unknown operation: {op_name}"
        
        # 检查必填参数
        for pname, pdef in operation.params.items():
            if pdef.get("required", False) and pname not in params:
                return False, f"Missing required parameter: {pname}"
        
        # 检查类型和约束
        for pname, value in params.items():
            if pname not in operation.params:
                continue
            
            pdef = operation.params[pname]
            ptype = pdef.get("type")
            
            # 类型检查
            if ptype == "decimal" or ptype == "float":
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return False, f"Parameter {pname} must be a number"
                
                # 范围检查
                if "min" in pdef and value < pdef["min"]:
                    return False, f"Parameter {pname} must be >= {pdef['min']}"
                if "max" in pdef and value > pdef["max"]:
                    return False, f"Parameter {pname} must be <= {pdef['max']}"
            
            elif ptype == "integer":
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return False, f"Parameter {pname} must be an integer"
                
                if "min" in pdef and value < pdef["min"]:
                    return False, f"Parameter {pname} must be >= {pdef['min']}"
                if "max" in pdef and value > pdef["max"]:
                    return False, f"Parameter {pname} must be <= {pdef['max']}"
        
        return True, ""
    
    def check_preconditions(self, op_name: str, params: dict) -> tuple[bool, str]:
        """
        检查预条件
        
        Args:
            op_name: 操作名
            params: 参数字典
            
        Returns:
            (passed, error_message)
        """
        operation = self.operations.get(op_name)
        if not operation:
            return False, f"Unknown operation: {op_name}"
        
        for precond in operation.preconditions:
            sql = precond.get("sql", "")
            check_expr = precond.get("check", "")
            error_msg = precond.get("error", "Precondition check failed")
            
            if not sql:
                continue
            
            # 替换参数占位符
            sql, resolved_params = self._resolve_params(sql, params)
            
            try:
                result = self.db.execute(sql, resolved_params)
                
                if not result.rows:
                    return False, error_msg
                
                row = dict(zip(result.columns, result.rows[0]))
                
                # 执行检查表达式
                if not self._eval_check(check_expr, row, params):
                    return False, error_msg
            
            except Exception as e:
                return False, f"Precondition error: {e}"
        
        return True, ""
    
    def _resolve_params(self, sql: str, params: dict) -> tuple[str, dict]:
        """解析 SQL 中的参数占位符，未提供的参数绑定为 None"""
        resolved_params = {}
        pattern = r':(\w+)'
        
        def replace_param(m):
            key = m.group(1)
            resolved_params[key] = params.get(key, None)
            return f":{key}"
        
        resolved_sql = re.sub(pattern, replace_param, sql)
        return resolved_sql, resolved_params
    
    def _eval_check(self, expr: str, result_row: dict, params: dict) -> bool:
        """执行检查表达式"""
        if not expr:
            return True
        
        # 构建上下文
        context = {}
        context.update(result_row)
        context.update(params)
        
        # 简单的表达式求值
        try:
            # 替换 result.X 为 context 中对应的值名
            expr = re.sub(r'result\.(\w+)', r'\1', expr)
            # 替换 :param 为 param（参数引用）
            expr = re.sub(r':(\w+)', r'\1', expr)
            return eval(expr, {"__builtins__": {}}, context)
        except Exception:
            return False
    
    def execute(self, op_name: str, params: dict, 
                event_handler: Optional[Callable] = None) -> dict:
        """
        执行操作
        
        Args:
            op_name: 操作名
            params: 参数字典
            event_handler: 事件回调
            
        Returns:
            执行结果 {"status": "success"|"error", "data": ..., "error": ...}
        """
        operation = self.operations.get(op_name)
        if not operation:
            return {"status": "error", "error": f"Unknown operation: {op_name}"}
        
        # 1. 参数校验
        valid, error = self.validate_params(op_name, params)
        if not valid:
            return {"status": "error", "error": error}
        
        # 2. 预条件检查
        passed, error = self.check_preconditions(op_name, params)
        if not passed:
            return {"status": "error", "error": error}
        
        # 3. 生成自动参数
        resolved_params = self._generate_params(operation, params)
        
        # 4. 执行步骤
        try:
            with self.db.transaction():
                for step in operation.steps:
                    # 条件检查
                    if step.condition:
                        if not self._eval_check(step.condition, {}, resolved_params):
                            continue
                    
                    sql, step_params = self._resolve_params(step.sql, resolved_params)
                    self.db.execute(sql, step_params)
                
                # 5. 发布效果事件
                self._publish_effects(operation, resolved_params)
                
                return {"status": "success", "data": resolved_params}
        
        except Exception as e:
            # 6. 执行补偿
            self._execute_compensation(operation, resolved_params)
            return {"status": "error", "error": str(e)}
    
    def _generate_params(self, operation: OperationDef, params: dict) -> dict:
        """生成自动参数（如 UUID）"""
        resolved = dict(params)
        
        for step in operation.steps:
            for pname, gen_type in step.generate.items():
                if pname in resolved:
                    continue
                    
                if gen_type == "uuid":
                    resolved[pname] = str(uuid.uuid4())
                elif gen_type == "now":
                    from datetime import datetime
                    resolved[pname] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return resolved
    
    def _publish_effects(self, operation: OperationDef, params: dict) -> None:
        """发布效果事件"""
        for effect in operation.effects:
            event_name = effect.get("event")
            event_data = {}
            
            # 解析事件数据
            for key, value in effect.get("data", {}).items():
                if isinstance(value, str) and value.startswith(":"):
                    param_name = value[1:]
                    event_data[key] = params.get(param_name, value)
                else:
                    event_data[key] = value
            
            # 调用注册的处理器
            if event_name in self._effect_handlers:
                for handler in self._effect_handlers[event_name]:
                    handler(event_data)
    
    def _execute_compensation(self, operation: OperationDef, params: dict) -> None:
        """执行补偿"""
        if not operation.compensation:
            return
        
        for comp in operation.compensation:
            sql = comp.get("sql", "")
            if not sql:
                continue
            
            sql, comp_params = self._resolve_params(sql, params)
            try:
                self.db.execute(sql, comp_params)
            except Exception:
                # 补偿失败只记录日志
                pass
    
    def register_effect_handler(self, event_name: str, handler: Callable) -> None:
        """注册效果处理器"""
        if event_name not in self._effect_handlers:
            self._effect_handlers[event_name] = []
        self._effect_handlers[event_name].append(handler)
    
    def get_risk_level(self, op_name: str) -> RiskLevel:
        """获取操作风险等级"""
        operation = self.operations.get(op_name)
        if not operation:
            return RiskLevel.MEDIUM
        
        level = operation.risk_level.lower()
        if level == "low":
            return RiskLevel.LOW
        elif level == "high":
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
    
    def is_read_only(self, op_name: str) -> bool:
        """判断是否只读操作"""
        operation = self.operations.get(op_name)
        return operation.read_only if operation else False
