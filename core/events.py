"""
Events Module - 事件发布/订阅

设计原则:
- 事件驱动架构
- 支持同步/异步处理器
- 简单可靠
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict


@dataclass
class Event:
    """事件"""
    name: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""


EventHandler = Callable[[Event], Any]
AsyncEventHandler = Callable[[Event], Awaitable[Any]]


class EventBus:
    """
    事件总线 - 发布/订阅模式
    
    用法:
        # 订阅
        def on_coupon_issued(event):
            print(f"Coupon issued: {event.data}")
        
        events.subscribe("coupon_issued", on_coupon_issued)
        
        # 发布
        events.publish(Event("coupon_issued", {"coupon_id": "xxx"}))
    """
    
    def __init__(self):
        """初始化事件总线"""
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._async_handlers: dict[str, list[AsyncEventHandler]] = defaultdict(list)
        self._event_history: list[Event] = []
        self._max_history = 100
    
    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """
        订阅事件
        
        Args:
            event_name: 事件名
            handler: 处理函数
        """
        self._handlers[event_name].append(handler)
    
    def subscribe_async(self, event_name: str, handler: AsyncEventHandler) -> None:
        """
        订阅异步事件
        
        Args:
            event_name: 事件名
            handler: 异步处理函数
        """
        self._async_handlers[event_name].append(handler)
    
    def unsubscribe(self, event_name: str, handler: EventHandler) -> bool:
        """
        取消订阅
        
        Args:
            event_name: 事件名
            handler: 处理函数
            
        Returns:
            是否成功取消
        """
        if event_name in self._handlers:
            try:
                self._handlers[event_name].remove(handler)
                return True
            except ValueError:
                pass
        return False
    
    def publish(self, event: Event) -> list[Any]:
        """
        发布事件（同步）
        
        Args:
            event: 事件对象
            
        Returns:
            处理结果列表
        """
        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        results = []
        
        # 调用同步处理器
        for handler in self._handlers.get(event.name, []):
            try:
                result = handler(event)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        
        return results
    
    async def publish_async(self, event: Event) -> list[Any]:
        """
        发布事件（异步）
        
        Args:
            event: 事件对象
            
        Returns:
            处理结果列表
        """
        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        results = []
        
        # 调用同步处理器
        for handler in self._handlers.get(event.name, []):
            try:
                result = handler(event)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        
        # 调用异步处理器
        for handler in self._async_handlers.get(event.name, []):
            try:
                result = await handler(event)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        
        return results
    
    def emit(self, event_name: str, data: dict = None, source: str = "") -> list[Any]:
        """
        快捷发布方法
        
        Args:
            event_name: 事件名
            data: 事件数据
            source: 事件源
            
        Returns:
            处理结果列表
        """
        event = Event(
            name=event_name,
            data=data or {},
            source=source,
        )
        return self.publish(event)
    
    def get_handlers(self, event_name: str) -> list[EventHandler]:
        """获取事件的所有处理器"""
        return list(self._handlers.get(event_name, []))
    
    def get_history(self, event_name: str | None = None, limit: int = 10) -> list[Event]:
        """
        获取事件历史
        
        Args:
            event_name: 事件名过滤（可选）
            limit: 返回数量
            
        Returns:
            事件列表
        """
        history = self._event_history
        
        if event_name:
            history = [e for e in history if e.name == event_name]
        
        return history[-limit:]
    
    def clear(self) -> None:
        """清空所有订阅"""
        self._handlers.clear()
        self._async_handlers.clear()
        self._event_history.clear()
    
    def listener_count(self, event_name: str) -> int:
        """获取事件监听器数量"""
        return len(self._handlers.get(event_name, [])) + \
               len(self._async_handlers.get(event_name, []))
