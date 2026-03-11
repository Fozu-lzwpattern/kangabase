"""
KangaBase Core Module
"""

from .database import Database, QueryResult, StorageAdapter
from .schema import SchemaManager, EntityDef, FieldDef, SchemaValidationError
from .contract import ContractExecutor, OperationDef, ContractError, PreconditionError, RiskLevel
from .intent import IntentRegistry, IntentMatch
from .policy import PolicyEngine, PolicyResult, PolicyDecision, PolicyError
from .sandbox import Sandbox
from .audit import AuditLogger, AuditEntry, AuditStatus
from .events import EventBus, Event

__all__ = [
    "Database",
    "QueryResult",
    "StorageAdapter",
    "SchemaManager",
    "EntityDef", 
    "FieldDef",
    "SchemaValidationError",
    "ContractExecutor",
    "OperationDef",
    "ContractError",
    "PreconditionError",
    "RiskLevel",
    "IntentRegistry",
    "IntentMatch",
    "PolicyEngine",
    "PolicyResult",
    "PolicyDecision",
    "PolicyError",
    "Sandbox",
    "AuditLogger",
    "AuditEntry",
    "AuditStatus",
    "EventBus",
    "Event",
]
