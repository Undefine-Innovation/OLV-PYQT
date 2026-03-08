#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置同步服务
提供配置变更的实时同步和事件通知功能
确保提示词修改能够自动同步到所有相关配置
"""

import time
from typing import Dict, Any, List, Callable, Optional
from pathlib import Path
from threading import Lock
from .config_manager import get_config_manager
from .config_logger import get_config_logger


class ConfigSyncEvent:
    """配置同步事件"""
    
    def __init__(self, event_type: str, config_type: str, old_value: Any, new_value: Any, timestamp: float = None):
        self.event_type = event_type  # 'update', 'sync', 'error'
        self.config_type = config_type  # 'system_prompt', 'character_prompt', etc.
        self.old_value = old_value
        self.new_value = new_value
        self.timestamp = timestamp or time.time()
        self.success = True
        self.error_message = None


class ConfigSyncService:
    """配置同步服务"""
    
    def __init__(self):
        self.config_manager = get_config_manager()
        self.logger = get_config_logger()
        self._listeners: List[Callable[[ConfigSyncEvent], None]] = []
        self._sync_lock = Lock()
        self._sync_history: List[ConfigSyncEvent] = []
        self._max_history = 100  # 最多保留100条历史记录
        
        # 记录服务启动
        self.logger.info("配置同步服务已启动")
    
    def add_listener(self, listener: Callable[[ConfigSyncEvent], None]):
        """添加配置变更监听器"""
        if listener not in self._listeners:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[ConfigSyncEvent], None]):
        """移除配置变更监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def _notify_listeners(self, event: ConfigSyncEvent):
        """通知所有监听器"""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"配置同步监听器异常", e, {
                    "listener": str(listener),
                    "event_type": event.event_type,
                    "config_type": event.config_type
                })
    
    def _add_to_history(self, event: ConfigSyncEvent):
        """添加到历史记录"""
        self._sync_history.append(event)
        # 保持历史记录数量限制
        if len(self._sync_history) > self._max_history:
            self._sync_history.pop(0)
    
    def sync_system_prompt(self, new_prompt: str, source: str = "unknown") -> ConfigSyncEvent:
        """同步系统提示词到所有相关配置"""
        start_time = time.time()
        
        with self._sync_lock:
            # 记录同步开始
            self.logger.sync_start("system_prompt", source)
            
            # 获取当前值
            try:
                current_config = self.config_manager.get_config_section("agent_config_template")
                old_prompt = current_config.get("system_prompt", "")
            except Exception as e:
                self.logger.error("获取当前系统提示词失败", e, {"source": source})
                old_prompt = ""
            
            # 创建同步事件
            event = ConfigSyncEvent(
                event_type="sync",
                config_type="system_prompt",
                old_value=old_prompt,
                new_value=new_prompt
            )
            
            try:
                # 验证输入
                if not isinstance(new_prompt, str):
                    raise ValueError(f"系统提示词必须是字符串类型，当前类型: {type(new_prompt)}")
                
                if len(new_prompt.strip()) == 0:
                    self.logger.warning("系统提示词为空", {"source": source})
                
                # 执行同步
                success = self.config_manager.update_system_prompt(new_prompt)
                event.success = success
                
                duration_ms = (time.time() - start_time) * 1000
                
                if success:
                    self.logger.sync_success("system_prompt", source, duration_ms)
                else:
                    event.error_message = "配置更新失败"
                    self.logger.sync_failure("system_prompt", source, "配置更新失败")
                
            except Exception as e:
                event.success = False
                event.error_message = str(e)
                self.logger.sync_failure("system_prompt", source, str(e), e)
            
            # 添加到历史记录
            self._add_to_history(event)
            
            # 通知监听器
            self._notify_listeners(event)
            
            return event
    
    def sync_character_prompt(self, character_name: str, new_prompt: str, source: str = "unknown") -> ConfigSyncEvent:
        """同步指定角色的提示词"""
        start_time = time.time()
        config_type = f"character_prompt_{character_name}"
        
        with self._sync_lock:
            # 记录同步开始
            self.logger.sync_start(config_type, source)
            
            # 获取当前值
            try:
                current_config = self.config_manager.get_character_config(character_name)
                old_prompt = current_config.get("system_prompt", "")
            except Exception as e:
                self.logger.error(f"获取角色 {character_name} 当前提示词失败", e, {"source": source})
                old_prompt = ""
            
            # 创建同步事件
            event = ConfigSyncEvent(
                event_type="sync",
                config_type=config_type,
                old_value=old_prompt,
                new_value=new_prompt
            )
            
            try:
                # 验证输入
                if not isinstance(character_name, str) or not character_name.strip():
                    raise ValueError(f"角色名称无效: {character_name}")
                
                if not isinstance(new_prompt, str):
                    raise ValueError(f"角色提示词必须是字符串类型，当前类型: {type(new_prompt)}")
                
                # 执行同步
                success = self.config_manager.update_character_prompt(character_name, new_prompt)
                event.success = success
                
                duration_ms = (time.time() - start_time) * 1000
                
                if success:
                    self.logger.sync_success(config_type, source, duration_ms)
                else:
                    event.error_message = "角色配置更新失败"
                    self.logger.sync_failure(config_type, source, "角色配置更新失败")
                
            except Exception as e:
                event.success = False
                event.error_message = str(e)
                self.logger.sync_failure(config_type, source, str(e), e)
            
            # 添加到历史记录
            self._add_to_history(event)
            
            # 通知监听器
            self._notify_listeners(event)
            
            return event
    
    def get_sync_history(self, limit: int = 10) -> List[ConfigSyncEvent]:
        """获取同步历史记录"""
        return self._sync_history[-limit:] if limit > 0 else self._sync_history.copy()
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        total_syncs = len(self._sync_history)
        successful_syncs = sum(1 for event in self._sync_history if event.success)
        failed_syncs = total_syncs - successful_syncs
        
        return {
            "total_syncs": total_syncs,
            "successful_syncs": successful_syncs,
            "failed_syncs": failed_syncs,
            "success_rate": successful_syncs / total_syncs if total_syncs > 0 else 0,
            "last_sync_time": self._sync_history[-1].timestamp if self._sync_history else None
        }
    
    def clear_history(self):
        """清空同步历史记录"""
        old_count = len(self._sync_history)
        self._sync_history.clear()
        self.logger.info(f"同步历史记录已清空，共清除 {old_count} 条记录")


# 全局配置同步服务实例
_config_sync_service = None


def get_config_sync_service() -> ConfigSyncService:
    """获取全局配置同步服务实例"""
    global _config_sync_service
    if _config_sync_service is None:
        _config_sync_service = ConfigSyncService()
    return _config_sync_service


# 便捷函数
def sync_system_prompt(new_prompt: str, source: str = "unknown") -> bool:
    """便捷函数：同步系统提示词"""
    service = get_config_sync_service()
    event = service.sync_system_prompt(new_prompt, source)
    return event.success


def sync_character_prompt(character_name: str, new_prompt: str, source: str = "unknown") -> bool:
    """便捷函数：同步角色提示词"""
    service = get_config_sync_service()
    event = service.sync_character_prompt(character_name, new_prompt, source)
    return event.success