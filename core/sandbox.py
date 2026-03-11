"""
Sandbox Module - 沙箱预执行

设计原则:
- 预执行验证：在 :memory: 数据库中模拟执行
- 验证 SQL 正确性
- 验证参数合法性
- 不影响主数据库
"""

from __future__ import annotations

from typing import Any, Optional
from contextlib import contextmanager
from ..core.database import Database


class Sandbox:
    """
    沙箱预执行器
    
    用途:
    1. 预执行 SQL 验证正确性
    2. 模拟事务执行效果
    3. 在不影响主数据库的情况下测试操作
    """
    
    def __init__(self, main_db: Database):
        """
        初始化沙箱
        
        Args:
            main_db: 主数据库实例（用于复制 schema）
        """
        self.main_db = main_db
        self.sandbox_db = Database(":memory:")
        self._initialized = False
    
    def initialize(self) -> None:
        """从主数据库复制 Schema 到沙箱"""
        if self._initialized:
            return
        
        # 复制表结构
        tables = self.main_db.list_tables()
        for table in tables:
            if table.startswith("_"):
                continue  # 跳过内部表
            
            # 获取建表语句
            sql = f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'"
            result = self.main_db.execute(sql)
            
            if result.rows:
                create_sql = result.rows[0][0]
                # 确保使用 IF NOT EXISTS
                if "IF NOT EXISTS" not in create_sql:
                    create_sql = create_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
                self.sandbox_db.execute(create_sql)
        
        self._initialized = True
    
    def reset(self) -> None:
        """重置沙箱"""
        self.sandbox_db.close()
        self.sandbox_db = Database(":memory:")
        self._initialized = False
    
    @contextmanager
    def session(self):
        """
        沙箱会话上下文
        
        用法:
            with sandbox.session() as db:
                db.execute(...)
        """
        if not self._initialized:
            self.initialize()
        
        try:
            yield self.sandbox_db
        finally:
            pass  # 不提交，保持只读
    
    def dry_run(self, sql: str, params: dict | tuple = ()) -> dict:
        """
        试运行 SQL
        
        Args:
            sql: SQL 语句
            params: 参数
            
        Returns:
            {"valid": bool, "error": str|None, "result": QueryResult}
        """
        if not self._initialized:
            self.initialize()
        
        try:
            result = self.sandbox_db.execute(sql, params)
            return {
                "valid": True,
                "error": None,
                "result": result,
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "result": None,
            }
    
    def simulate(self, operations: list[tuple[str, dict]]) -> dict:
        """
        模拟一系列操作
        
        Args:
            operations: [(sql, params), ...]
            
        Returns:
            {"success": bool, "results": [...], "error": str|None}
        """
        if not self._initialized:
            self.initialize()
        
        results = []
        
        try:
            for sql, params in operations:
                result = self.sandbox_db.execute(sql, params)
                results.append(result)
            
            return {
                "success": True,
                "results": results,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "results": results,
                "error": str(e),
            }
    
    def verify_contract(self, contract_exec, op_name: str, params: dict) -> dict:
        """
        验证契约可执行性
        
        Args:
            contract_exec: ContractExecutor 实例
            op_name: 操作名
            params: 参数
            
        Returns:
            {"can_execute": bool, "precond_errors": [...], "sql_errors": [...]}
        """
        if not self._initialized:
            self.initialize()
        
        operation = contract_exec.get_operation(op_name)
        if not operation:
            return {
                "can_execute": False,
                "precond_errors": [f"Unknown operation: {op_name}"],
                "sql_errors": [],
            }
        
        precond_errors = []
        sql_errors = []
        
        # 1. 预条件检查（沙箱执行）
        for precond in operation.preconditions:
            sql = precond.get("sql", "")
            if not sql:
                continue
            
            try:
                result = self.sandbox_db.execute(sql, params)
                if not result.rows:
                    precond_errors.append(precond.get("error", "Precondition failed"))
            except Exception as e:
                precond_errors.append(f"Precondition SQL error: {e}")
        
        # 2. 步骤执行检查
        for step in operation.steps:
            sql = step.sql
            try:
                resolved_params = self._resolve_params(sql, params)
                self.sandbox_db.execute(sql, resolved_params)
            except Exception as e:
                sql_errors.append(f"Step SQL error: {e}")
        
        return {
            "can_execute": len(precond_errors) == 0 and len(sql_errors) == 0,
            "precond_errors": precond_errors,
            "sql_errors": sql_errors,
        }
    
    def _resolve_params(self, sql: str, params: dict) -> dict:
        """简单参数解析"""
        import re
        pattern = r':(\w+)'
        resolved = {}
        
        for match in re.finditer(pattern, sql):
            key = match.group(1)
            if key in params:
                resolved[key] = params[key]
        
        return resolved
    
    def close(self):
        """关闭沙箱"""
        self.sandbox_db.close()
