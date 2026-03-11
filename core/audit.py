"""
Audit Module - 审计日志

设计原则:
- 记录所有 Agent 操作
- 完整审计追踪
- 风险评分
- 支持查询和统计
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class AuditStatus(Enum):
    """审计状态"""
    SUCCESS = "success"
    FAILED = "failed"
    DENIED = "denied"
    SANDBOX = "sandbox"


@dataclass
class AuditEntry:
    """审计条目"""
    id: str
    timestamp: datetime
    agent_id: str
    agent_role: str
    session_id: str
    intent_name: str
    intent_params: str
    intent_source: str  # structured, nl, llm
    sql_executed: str
    affected_rows: int
    execution_ms: float
    risk_score: float
    sandbox_used: bool
    human_confirmed: bool
    status: str
    error_message: Optional[str] = None


class AuditLogger:
    """
    审计日志记录器
    
    记录所有操作到 _audit_log 表
    """
    
    TABLE_NAME = "_audit_log"
    
    def __init__(self, db):
        """
        初始化审计日志
        
        Args:
            db: Database 实例
        """
        self.db = db
        self._ensure_table()

    def _ensure_table(self):
        """确保审计表存在"""
        self.db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                id TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                agent_id TEXT NOT NULL,
                agent_role TEXT,
                session_id TEXT,
                intent_name TEXT NOT NULL,
                intent_params TEXT,
                intent_source TEXT DEFAULT 'structured',
                sql_executed TEXT,
                affected_rows INTEGER,
                execution_ms REAL,
                risk_score REAL,
                sandbox_used INTEGER DEFAULT 0,
                human_confirmed INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            )
        """)
    
    def log(self, agent_id: str, intent_name: str,
            intent_params: dict | str,
            status: AuditStatus | str,
            session_id: str = "",
            agent_role: str = "",
            intent_source: str = "structured",
            sql_executed: str = "",
            affected_rows: int = 0,
            execution_ms: float = 0.0,
            risk_score: float = 0.0,
            sandbox_used: bool = False,
            human_confirmed: bool = False,
            error_message: str = None) -> str:
        """
        记录审计日志
        
        Args:
            agent_id: Agent ID
            intent_name: 操作名
            intent_params: 参数
            status: 状态
            session_id: 会话 ID
            agent_role: 角色
            intent_source: 来源 (structured/nl/llm)
            sql_executed: 执行的 SQL
            affected_rows: 影响行数
            execution_ms: 执行耗时(毫秒)
            risk_score: 风险评分
            sandbox_used: 是否使用沙箱
            human_confirmed: 是否人工确认
            error_message: 错误信息
            
        Returns:
            audit_id
        """
        audit_id = str(uuid.uuid4())
        
        # 序列化参数
        if isinstance(intent_params, dict):
            import json
            params_str = json.dumps(intent_params)
        else:
            params_str = str(intent_params)
        
        sql = f"""
        INSERT INTO {self.TABLE_NAME} (
            id, agent_id, agent_role, session_id, intent_name, intent_params,
            intent_source, sql_executed, affected_rows, execution_ms,
            risk_score, sandbox_used, human_confirmed, status, error_message
        ) VALUES (
            :id, :agent_id, :agent_role, :session_id, :intent_name, :intent_params,
            :intent_source, :sql_executed, :affected_rows, :execution_ms,
            :risk_score, :sandbox_used, :human_confirmed, :status, :error_message
        )
        """
        
        self.db.execute(sql, {
            "id": audit_id,
            "agent_id": agent_id,
            "agent_role": agent_role,
            "session_id": session_id,
            "intent_name": intent_name,
            "intent_params": params_str,
            "intent_source": intent_source,
            "sql_executed": sql_executed,
            "affected_rows": affected_rows,
            "execution_ms": execution_ms,
            "risk_score": risk_score,
            "sandbox_used": 1 if sandbox_used else 0,
            "human_confirmed": 1 if human_confirmed else 0,
            "status": status.value if isinstance(status, AuditStatus) else status,
            "error_message": error_message,
        })
        
        return audit_id
    
    def query(self, agent_id: str | None = None,
              intent_name: str | None = None,
              status: str | None = None,
              session_id: str | None = None,
              since: datetime | None = None,
              until: datetime | None = None,
              limit: int = 100) -> list[AuditEntry]:
        """
        查询审计日志
        
        Args:
            agent_id: Agent ID 过滤
            intent_name: 操作名过滤
            status: 状态过滤
            session_id: 会话 ID 过滤
            since: 开始时间
            until: 结束时间
            limit: 返回数量限制
            
        Returns:
            审计条目列表
        """
        conditions = []
        params = {}
        
        if agent_id:
            conditions.append("agent_id = :agent_id")
            params["agent_id"] = agent_id
        
        if intent_name:
            conditions.append("intent_name = :intent_name")
            params["intent_name"] = intent_name
        
        if status:
            conditions.append("status = :status")
            params["status"] = status
        
        if session_id:
            conditions.append("session_id = :session_id")
            params["session_id"] = session_id
        
        if since:
            conditions.append("timestamp >= :since")
            params["since"] = since.isoformat()
        
        if until:
            conditions.append("timestamp <= :until")
            params["until"] = until.isoformat()
        
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            {where}
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        params["limit"] = limit
        
        result = self.db.execute(sql, params)
        
        entries = []
        for row in result.rows:
            entries.append(self._row_to_entry(row, result.columns))
        
        return entries
    
    def _row_to_entry(self, row: tuple, columns: list[str]) -> AuditEntry:
        """行数据转 AuditEntry"""
        data = dict(zip(columns, row))
        
        return AuditEntry(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            agent_id=data["agent_id"],
            agent_role=data.get("agent_role", ""),
            session_id=data.get("session_id", ""),
            intent_name=data["intent_name"],
            intent_params=data.get("intent_params", ""),
            intent_source=data.get("intent_source", "structured"),
            sql_executed=data.get("sql_executed", ""),
            affected_rows=data.get("affected_rows", 0),
            execution_ms=data.get("execution_ms", 0.0),
            risk_score=data.get("risk_score", 0.0),
            sandbox_used=bool(data.get("sandbox_used", 0)),
            human_confirmed=bool(data.get("human_confirmed", 0)),
            status=data["status"],
            error_message=data.get("error_message"),
        )
    
    def get_statistics(self, since: datetime | None = None) -> dict:
        """
        获取统计信息
        
        Args:
            since: 统计开始时间
            
        Returns:
            统计数据
        """
        where = ""
        params = {}
        
        if since:
            where = "WHERE timestamp >= :since"
            params["since"] = since.isoformat()
        
        # 总数
        sql = f"SELECT COUNT(*) FROM {self.TABLE_NAME} {where}"
        result = self.db.execute(sql, params)
        total = result.rows[0][0] if result.rows else 0
        
        # 按状态统计
        sql = f"""
            SELECT status, COUNT(*) as cnt 
            FROM {self.TABLE_NAME} 
            {where}
            GROUP BY status
        """
        result = self.db.execute(sql, params)
        by_status = {row[0]: row[1] for row in result.rows}
        
        # 按 Agent 统计
        sql = f"""
            SELECT agent_id, COUNT(*) as cnt 
            FROM {self.TABLE_NAME} 
            {where}
            GROUP BY agent_id
        """
        result = self.db.execute(sql, params)
        by_agent = {row[0]: row[1] for row in result.rows}
        
        # 按操作统计
        sql = f"""
            SELECT intent_name, COUNT(*) as cnt 
            FROM {self.TABLE_NAME} 
            {where}
            GROUP BY intent_name
        """
        result = self.db.execute(sql, params)
        by_operation = {row[0]: row[1] for row in result.rows}
        
        return {
            "total": total,
            "by_status": by_status,
            "by_agent": by_agent,
            "by_operation": by_operation,
        }
    
    def clear(self, before: datetime | None = None) -> int:
        """
        清理旧日志
        
        Args:
            before: 删除此时间之前的日志
            
        Returns:
            删除的行数
        """
        if not before:
            before = datetime.now() - timedelta(days=30)
        
        sql = f"DELETE FROM {self.TABLE_NAME} WHERE timestamp < :before"
        result = self.db.execute(sql, {"before": before.isoformat()})
        return result.rowcount
