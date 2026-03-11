"""
Database Module - SQLite 封装 + Storage Adapter

设计原则 (D. Richard Hipp):
- 极致简洁：正确性至上
- 关注分离：Storage Adapter 抽象，后期可切换 libSQL
"""

from __future__ import annotations

import sqlite3
import uuid
import threading
from pathlib import Path
from typing import Any, Optional, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime


@dataclass
class QueryResult:
    """查询结果封装"""
    columns: list[str]
    rows: list[tuple]
    rowcount: int
    lastrowid: int | None
    
    def __iter__(self):
        """支持迭代"""
        return iter(self.rows)
    
    def as_dicts(self) -> list[dict]:
        """转换为字典列表"""
        return [dict(zip(self.columns, row)) for row in self.rows]
    
    def first(self) -> Optional[dict]:
        """获取第一行"""
        if self.rows:
            return dict(zip(self.columns, self.rows[0]))
        return None


class Database:
    """
    SQLite 数据库封装 + Storage Adapter
    
    特性:
    - 线程安全连接
    - 上下文管理器支持
    - 参数化查询防注入
    - 结果封装
    """
    
    def __init__(self, db_path: str | Path | None = None, in_memory: bool = False):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径 (None 则创建临时数据库)
            in_memory: 是否使用内存数据库
        """
        self.db_path = Path(db_path) if db_path else None
        self.in_memory = in_memory
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # 初始化审计表
        self._init_audit_table()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地的连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            if self.in_memory or (self.db_path and str(self.db_path) == ":memory:"):
                self._local.conn = sqlite3.connect(":memory:", check_same_thread=False)
            elif self.db_path:
                self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            else:
                self._local.conn = sqlite3.connect(":memory:", check_same_thread=False)
            
            # 启用外键约束
            self._local.conn.execute("PRAGMA foreign_keys = ON")
            # 返回字典类型
            self._local.conn.row_factory = sqlite3.Row
        
        return self._local.conn
    
    def _init_audit_table(self):
        """初始化审计表"""
        sql = """
        CREATE TABLE IF NOT EXISTS _audit_log (
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
        """
        # 使用主连接执行，确保表在同一个数据库中
        conn = self._get_connection()
        conn.execute(sql)
        conn.commit()
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def execute(self, sql: str, params: dict | tuple = ()) -> QueryResult:
        """
        执行单条 SQL
        
        Args:
            sql: SQL 语句 (使用 :param 命名参数)
            params: 参数字典
            
        Returns:
            QueryResult 结果封装
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(sql, params if isinstance(params, dict) else params)
        
        # 获取列名
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        
        return QueryResult(
            columns=columns,
            rows=rows,
            rowcount=cursor.rowcount,
            lastrowid=cursor.lastrowid,
        )
    
    def execute_many(self, sql: str, params_list: Sequence[dict | tuple]) -> int:
        """
        批量执行 SQL
        
        Args:
            sql: SQL 语句
            params_list: 参数列表
            
        Returns:
            影响的行数
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.executemany(sql, params_list)
        return cursor.rowcount
    
    def executebatch(self, sql_list: list[tuple[str, dict | tuple]]) -> list[QueryResult]:
        """
        批量执行多条 SQL
        
        Args:
            sql_list: [(sql, params), ...] 列表
            
        Returns:
            QueryResult 列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        results = []
        
        for sql, params in sql_list:
            cursor.execute(sql, params if isinstance(params, dict) else params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            results.append(QueryResult(
                columns=columns,
                rows=rows,
                rowcount=cursor.rowcount,
                lastrowid=cursor.lastrowid,
            ))
        
        return results
    
    def create_table(self, name: str, columns: dict[str, str], 
                     primary_key: str = "id", if_not_exists: bool = True) -> None:
        """
        创建表
        
        Args:
            name: 表名
            columns: {column_name: type_def} 字典, 如 {"name": "TEXT", "age": "INTEGER"}
            primary_key: 主键列名
            if_not_exists: 是否添加 IF NOT EXISTS
        """
        cols = [f'"{col}" {typ}' for col, typ in columns.items()]
        cols.append(f'PRIMARY KEY ("{primary_key}")')
        
        sql = f"CREATE TABLE {'IF NOT EXISTS' if if_not_exists else ''} {name} ({', '.join(cols)})"
        self.execute(sql)
    
    def table_exists(self, name: str) -> bool:
        """检查表是否存在"""
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.execute(sql, (name,))
        return len(result.rows) > 0
    
    def drop_table(self, name: str) -> None:
        """删除表"""
        self.execute(f"DROP TABLE IF EXISTS {name}")
    
    def list_tables(self) -> list[str]:
        """列出所有表"""
        sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        return [row[0] for row in self.execute(sql)]
    
    def generate_uuid(self) -> str:
        """生成 UUID"""
        return str(uuid.uuid4())
    
    def now(self) -> str:
        """获取当前时间戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def close(self):
        """关闭连接"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


class StorageAdapter:
    """
    Storage Adapter 抽象 - 后期可切换 libSQL
    
    当前使用 SQLite 标准库，后期只需修改此类即可切换到 libSQL
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    def read(self, table: str, conditions: dict | None = None, 
             order_by: str | None = None, limit: int | None = None) -> list[dict]:
        """
        读取数据
        
        Args:
            table: 表名
            conditions: 过滤条件 {"column": value}
            order_by: 排序 "column ASC"
            limit: 限制数量
            
        Returns:
            字典列表
        """
        sql = f"SELECT * FROM {table}"
        params = {}
        
        if conditions:
            where_clauses = [f"{k} = :{k}" for k in conditions.keys()]
            sql += " WHERE " + " AND ".join(where_clauses)
            params = conditions
        
        if order_by:
            sql += f" ORDER BY {order_by}"
        
        if limit:
            sql += f" LIMIT {limit}"
        
        result = self.db.execute(sql, params)
        return result.as_dicts()
    
    def write(self, table: str, data: dict) -> str:
        """
        写入数据
        
        Args:
            table: 表名
            data: 要写入的数据
            
        Returns:
            插入行的 id
        """
        columns = list(data.keys())
        placeholders = [f":{col}" for col in columns]
        
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        result = self.db.execute(sql, data)
        return str(result.lastrowid) if result.lastrowid else ""
    
    def update(self, table: str, data: dict, conditions: dict) -> int:
        """
        更新数据
        
        Args:
            table: 表名
            data: 要更新的数据
            conditions: 过滤条件
            
        Returns:
            影响的行数
        """
        set_clauses = [f"{k} = :set_{k}" for k in data.keys()]
        where_clauses = [f"{k} = :where_{k}" for k in conditions.keys()]
        
        sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
        
        # 合并参数
        params = {f"set_{k}": v for k, v in data.items()}
        params.update({f"where_{k}": v for k, v in conditions.items()})
        
        result = self.db.execute(sql, params)
        return result.rowcount
    
    def delete(self, table: str, conditions: dict) -> int:
        """
        删除数据
        
        Args:
            table: 表名
            conditions: 过滤条件
            
        Returns:
            影响的行数
        """
        where_clauses = [f"{k} = :{k}" for k in conditions.keys()]
        sql = f"DELETE FROM {table} WHERE {' AND '.join(where_clauses)}"
        
        result = self.db.execute(sql, conditions)
        return result.rowcount
