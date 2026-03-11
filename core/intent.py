"""
Intent Module - Intent Registry (架构枢纽)

设计原则:
- Intent Registry 是架构枢纽：同时承担意图路由和安全白名单
- 模式匹配：支持 NL 模式 -> 操作名的映射
- 预留 LLM 接口：未来可接入语义理解
"""

from __future__ import annotations

import re
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class IntentMatch:
    """意图匹配结果"""
    operation: str
    confidence: float
    params: dict[str, Any]
    pattern: str


class IntentRegistry:
    """
    Intent Registry - 意图路由 + 安全白名单
    
    核心职责:
    1. 注册 intent pattern -> operation 的映射
    2. 解析自然语言意图
    3. 提供安全白名单（只有注册的操作才能执行）
    """
    
    def __init__(self):
        """初始化 Intent Registry"""
        # pattern -> operation 映射
        self._patterns: dict[str, str] = {}
        
        # operation -> [patterns] 反向索引
        self._operation_patterns: dict[str, list[str]] = {}
        
        # 参数提取器 {pattern: {param_name: regex_group}}
        self._param_extractors: dict[str, dict[str, str]] = {}
        
        # 已注册的操作白名单
        self._whitelist: set[str] = set()
    
    def register(self, pattern: str, operation: str) -> "IntentRegistry":
        """
        注册意图模式
        
        Args:
            pattern: 意图模式，支持 {param} 占位符
                    如 "发券给{user_id}" -> operation="issue_coupon"
            operation: 操作名
            
        Returns:
            self (链式调用)
        """
        self._patterns[pattern] = operation
        self._whitelist.add(operation)
        
        if operation not in self._operation_patterns:
            self._operation_patterns[operation] = []
        self._operation_patterns[operation].append(pattern)
        
        # 解析参数提取器
        self._param_extractors[pattern] = self._parse_pattern(pattern)
        
        return self
    
    def _parse_pattern(self, pattern: str) -> dict[str, str]:
        """解析模式，提取参数名"""
        # 匹配 {param_name}
        param_names = re.findall(r'\{(\w+)\}', pattern)
        
        # 生成正则表达式
        regex_pattern = pattern
        extractors = {}
        
        for name in param_names:
            # 将 {name} 替换为正则捕获组
            regex_pattern = regex_pattern.replace(
                f'{{{name}}}', 
                f'(?P<{name}>[^\\s]+)'
            )
            extractors[name] = name
        
        return {
            "regex": re.compile(regex_pattern),
            "params": extractors
        }
    
    def match(self, text: str) -> Optional[IntentMatch]:
        """
        匹配意图
        
        Args:
            text: 用户输入的自然语言
            
        Returns:
            IntentMatch 或 None
        """
        # 清理文本
        text = text.strip()
        
        best_match: Optional[IntentMatch] = None
        
        for pattern, extractor in self._param_extractors.items():
            regex = extractor["regex"]
            param_names = extractor["params"]
            
            match = regex.search(text)
            if match:
                # 提取参数
                params = match.groupdict()
                
                # 计算置信度（简单实现：完全匹配=1.0，部分匹配=0.8）
                confidence = 0.8 if match.group() != text else 1.0
                
                best_match = IntentMatch(
                    operation=self._patterns[pattern],
                    confidence=confidence,
                    params=params,
                    pattern=pattern
                )
                break
        
        return best_match
    
    def resolve(self, text: str, strict: bool = False) -> Optional[str]:
        """
        解析意图，直接返回操作名
        
        Args:
            text: 用户输入
            strict: 是否严格匹配（完全相等）
            
        Returns:
            operation 名或 None
        """
        if strict:
            # 精确匹配
            for pattern, operation in self._patterns.items():
                if pattern == text:
                    return operation
            return None
        
        match = self.match(text)
        return match.operation if match else None
    
    def get_operation(self, name: str) -> Optional[str]:
        """
        获取已注册的操作名（白名单检查）
        
        Args:
            name: 操作名
            
        Returns:
            操作名（如果在白名单中）或 None
        """
        if name in self._whitelist:
            return name
        return None
    
    def is_allowed(self, operation: str) -> bool:
        """检查操作是否在白名单中"""
        return operation in self._whitelist
    
    def list_operations(self) -> list[str]:
        """列出所有已注册的操作"""
        return sorted(list(self._whitelist))
    
    def get_patterns(self, operation: str) -> list[str]:
        """获取操作对应的所有模式"""
        return self._operation_patterns.get(operation, [])
    
    def remove(self, operation: str) -> bool:
        """
        移除操作及其所有模式
        
        Args:
            operation: 操作名
            
        Returns:
            是否成功移除
        """
        if operation not in self._whitelist:
            return False
        
        patterns = self._operation_patterns.pop(operation, [])
        for pattern in patterns:
            self._patterns.pop(pattern, None)
            self._param_extractors.pop(pattern, None)
        
        self._whitelist.discard(operation)
        return True
    
    def clear(self) -> None:
        """清空所有注册"""
        self._patterns.clear()
        self._operation_patterns.clear()
        self._param_extractors.clear()
        self._whitelist.clear()
    
    # === LLM 接口预留 ===
    
    async def match_with_llm(self, text: str, llm_client: Any = None) -> Optional[IntentMatch]:
        """
        使用 LLM 进行意图匹配（预留接口）
        
        Args:
            text: 用户输入
            llm_client: LLM 客户端（可选）
            
        Returns:
            IntentMatch 或 None
        """
        # TODO: 实现 LLM 语义理解
        # 1. 构建 prompt，说明可用的操作和参数
        # 2. 调用 LLM
        # 3. 解析返回的操作名和参数
        
        # 暂时回退到规则匹配
        return self.match(text)
    
    def to_dict(self) -> dict:
        """导出注册表"""
        return {
            "whitelist": list(self._whitelist),
            "mappings": [
                {"pattern": p, "operation": o}
                for p, o in self._patterns.items()
            ]
        }
