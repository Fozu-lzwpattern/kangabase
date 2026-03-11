"""
NL Parser Module - 自然语言意图解析

设计原则:
- 模式匹配为主（当前实现）
- 预留 LLM 接口（未来扩展）
- 同义词支持
"""

from __future__ import annotations

import re
from typing import Any, Optional


class NLPException(Exception):
    """NL 解析异常"""
    pass


class NLParser:
    """
    自然语言意图解析器
    
    当前实现：基于模式匹配
    未来扩展：接入 LLM 语义理解
    """
    
    def __init__(self, intent_registry):
        """
        初始化 NL 解析器
        
        Args:
            intent_registry: IntentRegistry 实例
        """
        self.intent_registry = intent_registry
    
    def parse(self, text: str) -> dict:
        """
        解析自然语言
        
        Args:
            text: 用户输入
            
        Returns:
            {
                "intent": "operation_name",
                "confidence": 0.8,
                "params": {...},
                "raw": "..."
            }
        """
        # 预处理
        text = self._preprocess(text)
        
        # 尝试模式匹配
        match = self.intent_registry.match(text)
        
        if match:
            return {
                "intent": match.operation,
                "confidence": match.confidence,
                "params": match.params,
                "raw": text,
            }
        
        # 无法解析
        return {
            "intent": None,
            "confidence": 0.0,
            "params": {},
            "raw": text,
            "error": "Cannot understand input",
        }
    
    def _preprocess(self, text: str) -> str:
        """预处理文本"""
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 统一标点
        text = text.replace('？', '?').replace('！', '!')
        
        return text
    
    async def parse_with_llm(self, text: str, llm_client: Any = None) -> dict:
        """
        使用 LLM 解析（预留接口）
        
        Args:
            text: 用户输入
            llm_client: LLM 客户端
            
        Returns:
            解析结果
        """
        # TODO: 实现 LLM 解析
        # 1. 构建 prompt，包含可用操作列表
        # 2. 调用 LLM
        # 3. 解析返回的 JSON
        
        # 暂时回退到规则匹配
        return self.parse(text)
    
    def suggest(self, partial: str, limit: int = 5) -> list[dict]:
        """
        智能提示
        
        Args:
            partial: 部分输入
            limit: 返回数量
            
        Returns:
            建议列表
        """
        partial = partial.lower().strip()
        
        if not partial:
            # 返回前 N 个可用操作
            return [
                {"intent": op, "pattern": self.intent_registry.get_patterns(op)[0]}
                for op in self.intent_registry.list_operations()[:limit]
            ]
        
        suggestions = []
        
        # 匹配模式
        for op in self.intent_registry.list_operations():
            patterns = self.intent_registry.get_patterns(op)
            for pattern in patterns:
                if partial in pattern.lower():
                    suggestions.append({
                        "intent": op,
                        "pattern": pattern,
                        "match_type": "pattern",
                    })
                    break
        
        # 去重并返回
        seen = set()
        unique = []
        for s in suggestions:
            key = (s["intent"], s["pattern"])
            if key not in seen:
                seen.add(key)
                unique.append(s)
        
        return unique[:limit]
    
    def extract_entities(self, text: str, schema_manager) -> dict:
        """
        提取实体
        
        Args:
            text: 用户输入
            schema_manager: SchemaManager 实例
            
        Returns:
            提取的实体
        """
        text = text.lower()
        
        entities = {}
        
        # 尝试匹配已知字段的同义词
        for field_name in schema_manager.entities.keys():
            entity = schema_manager.get_entity(field_name)
            if not entity:
                continue
            
            for fname, fdef in entity.fields.items():
                # 匹配同义词
                for syn in fdef.synonyms:
                    if syn in text:
                        if field_name not in entities:
                            entities[field_name] = {}
                        # 尝试提取值
                        # 这里简化处理，实际需要更复杂的 NER
                        pass
        
        return entities
