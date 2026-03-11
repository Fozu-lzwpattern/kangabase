"""
Migrations Module - Schema + Contract 统一迁移

设计原则:
- 版本化管理
- 支持升级和回滚
- 统一迁移接口
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from dataclasses import dataclass, field


@dataclass
class Migration:
    """迁移定义"""
    version: str
    name: str
    up: Callable
    down: Callable = field(default=lambda: None)


class MigrationManager:
    """
    迁移管理器
    
    用法:
        mgr = MigrationManager(db, "./migrations")
        mgr.register("1.0", "init", up_func, down_func)
        mgr.migrate()
    """
    
    def __init__(self, db, migrations_dir: str | Path = "./migrations"):
        """
        初始化迁移管理器
        
        Args:
            db: Database 实例
            migrations_dir: 迁移文件目录
        """
        self.db = db
        self.migrations_dir = Path(migrations_dir)
        self.migrations: dict[str, Migration] = {}
        
        # 创建版本表
        self._ensure_table()
    
    def _ensure_table(self):
        """确保版本表存在"""
        if not self.db.table_exists("_schema_version"):
            self.db.execute("""
                CREATE TABLE _schema_version (
                    version TEXT PRIMARY KEY,
                    name TEXT,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    def register(self, version: str, name: str, up: Callable, down: Callable = None) -> None:
        """注册迁移"""
        self.migrations[version] = Migration(version, name, up, down)
    
    def get_current_version(self) -> str:
        """获取当前版本"""
        sql = "SELECT version FROM _schema_version ORDER BY applied_at DESC LIMIT 1"
        result = self.db.execute(sql)
        
        if result.rows:
            return result.rows[0][0]
        return "0.0.0"
    
    def get_pending_migrations(self) -> list[Migration]:
        """获取待执行的迁移"""
        current = self.get_current_version()
        
        pending = []
        for version, migration in sorted(self.migrations.items()):
            if version > current:
                pending.append(migration)
        
        return pending
    
    def migrate(self, target_version: str = None) -> dict:
        """
        执行迁移
        
        Args:
            target_version: 目标版本 (默认最新)
            
        Returns:
            {"success": bool, "applied": [...], "error": str|None}
        """
        if target_version is None:
            target_version = max(self.migrations.keys())
        
        pending = self.get_pending_migrations()
        
        # 过滤到目标版本
        pending = [m for m in pending if m.version <= target_version]
        
        applied = []
        
        for migration in pending:
            try:
                migration.up(self.db)
                
                # 记录版本
                self.db.execute(
                    "INSERT INTO _schema_version (version, name) VALUES (:v, :n)",
                    {"v": migration.version, "n": migration.name}
                )
                
                applied.append(migration.version)
            
            except Exception as e:
                return {
                    "success": False,
                    "applied": applied,
                    "error": f"Migration {migration.version} failed: {e}",
                }
        
        return {
            "success": True,
            "applied": applied,
            "error": None,
        }
    
    def rollback(self, steps: int = 1) -> dict:
        """
        回滚
        
        Args:
            steps: 回滚步数
            
        Returns:
            {"success": bool, "rolled_back": [...], "error": str|None}
        """
        current = self.get_current_version()
        
        if current == "0.0.0":
            return {"success": True, "rolled_back": [], "error": None}
        
        # 获取需要回滚的版本
        versions = sorted(self.migrations.keys(), reverse=True)
        to_rollback = []
        
        for v in versions:
            if v == current:
                to_rollback.append(v)
                break
        
        rolled_back = []
        
        for version in to_rollback:
            migration = self.migrations.get(version)
            if not migration or not migration.down:
                return {
                    "success": False,
                    "rolled_back": rolled_back,
                    "error": f"Migration {version} has no down function",
                }
            
            try:
                migration.down(self.db)
                
                # 删除版本记录
                self.db.execute(
                    "DELETE FROM _schema_version WHERE version = :v",
                    {"v": version}
                )
                
                rolled_back.append(version)
            
            except Exception as e:
                return {
                    "success": False,
                    "rolled_back": rolled_back,
                    "error": f"Rollback {version} failed: {e}",
                }
        
        return {
            "success": True,
            "rolled_back": rolled_back,
            "error": None,
        }
    
    def status(self) -> dict:
        """获取迁移状态"""
        current = self.get_current_version()
        pending = self.get_pending_migrations()
        
        return {
            "current_version": current,
            "latest_version": max(self.migrations.keys()) if self.migrations else "0.0.0",
            "pending_migrations": [m.version for m in pending],
            "total_migrations": len(self.migrations),
        }
