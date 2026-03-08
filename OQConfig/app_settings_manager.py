#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用设置管理器
管理应用级别的设置，如AI打断、静音等功能开关
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal


class AppSettingsManager(QObject):
    """应用设置管理器"""
    
    # 设置变化信号
    settingChanged = pyqtSignal(str, bool)  # 设置名称, 新值
    
    def __init__(self, config_dir: str = None):
        """
        初始化应用设置管理器
        
        Args:
            config_dir: 配置文件目录路径
        """
        super().__init__()
        
        # 获取当前文件所在目录
        current_dir = Path(__file__).parent
        self.config_dir = Path(config_dir) if config_dir else current_dir
        self.settings_file = self.config_dir / "app_settings.json"
        
        # 默认设置
        self._default_settings = {
            "ai_interrupt_enabled": False,
            "mute_on_ai_talk": False,
            "unmute_on_chat_end": True,
            "vad_sensitivity": 0.5,
            "auto_save_settings": True
        }
        
        # 当前设置缓存
        self._current_settings = None
        
        # 加载设置
        self.load_settings()
    
    def load_settings(self) -> bool:
        """
        加载应用设置
        
        Returns:
            bool: 加载是否成功
        """
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self._current_settings = json.load(f)
                    
                # 确保所有默认设置都存在
                for key, value in self._default_settings.items():
                    if key not in self._current_settings:
                        self._current_settings[key] = value
                        
                # 保存更新后的设置
                self.save_settings()
            else:
                # 使用默认设置
                self._current_settings = self._default_settings.copy()
                self.save_settings()
                
            return True
        except Exception as e:
            print(f"加载应用设置失败: {e}")
            self._current_settings = self._default_settings.copy()
            return False
    
    def save_settings(self) -> bool:
        """
        保存应用设置
        
        Returns:
            bool: 保存是否成功
        """
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._current_settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存应用设置失败: {e}")
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        获取设置值
        
        Args:
            key: 设置键名
            default: 默认值
            
        Returns:
            Any: 设置值
        """
        if self._current_settings is None:
            self.load_settings()
        
        return self._current_settings.get(key, default)
    
    def set_setting(self, key: str, value: Any, save_immediately: bool = True) -> bool:
        """
        设置值
        
        Args:
            key: 设置键名
            value: 设置值
            save_immediately: 是否立即保存
            
        Returns:
            bool: 设置是否成功
        """
        try:
            if self._current_settings is None:
                self.load_settings()
            
            old_value = self._current_settings.get(key)
            self._current_settings[key] = value
            
            if save_immediately:
                self.save_settings()
            
            # 发送设置变化信号
            if old_value != value:
                self.settingChanged.emit(key, value)
            
            return True
        except Exception as e:
            print(f"设置值失败: {e}")
            return False
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        获取所有设置
        
        Returns:
            Dict[str, Any]: 所有设置
        """
        if self._current_settings is None:
            self.load_settings()
        
        return self._current_settings.copy()
    
    def reset_to_defaults(self) -> bool:
        """
        重置为默认设置
        
        Returns:
            bool: 重置是否成功
        """
        try:
            self._current_settings = self._default_settings.copy()
            self.save_settings()
            
            # 发送所有设置变化信号
            for key, value in self._current_settings.items():
                self.settingChanged.emit(key, value)
            
            return True
        except Exception as e:
            print(f"重置设置失败: {e}")
            return False
    
    # 便捷方法
    def is_ai_interrupt_enabled(self) -> bool:
        """检查AI打断是否启用"""
        return self.get_setting("ai_interrupt_enabled", True)
    
    def set_ai_interrupt_enabled(self, enabled: bool) -> bool:
        """设置AI打断开关"""
        return self.set_setting("ai_interrupt_enabled", enabled)
    
    def is_mute_on_ai_talk(self) -> bool:
        """检查AI说话时是否静音"""
        return self.get_setting("mute_on_ai_talk", False)
    
    def set_mute_on_ai_talk(self, enabled: bool) -> bool:
        """设置AI说话时静音开关"""
        return self.set_setting("mute_on_ai_talk", enabled)
    
    def is_unmute_on_chat_end(self) -> bool:
        """检查聊天结束时是否取消静音"""
        return self.get_setting("unmute_on_chat_end", True)
    
    def set_unmute_on_chat_end(self, enabled: bool) -> bool:
        """设置聊天结束时取消静音开关"""
        return self.set_setting("unmute_on_chat_end", enabled)


# 全局应用设置管理器实例
_app_settings_manager = None


def get_app_settings_manager() -> AppSettingsManager:
    """
    获取全局应用设置管理器实例
    
    Returns:
        AppSettingsManager: 应用设置管理器实例
    """
    global _app_settings_manager
    if _app_settings_manager is None:
        _app_settings_manager = AppSettingsManager()
    return _app_settings_manager