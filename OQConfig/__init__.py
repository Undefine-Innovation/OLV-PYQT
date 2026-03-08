#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 从统一配置管理器导入所有接口
from .config_manager import (
    get_app_config_manager,
    get_config_manager,
    ConfigCenter,
    ConfigManager,
    AppConfigManager
)

# 为了向后兼容，保留原有的导入方式
# 这样现有代码无需修改即可继续工作
try:
    # 如果有人直接从原文件导入，提供兼容性支持
    from .config import ConfigCenter as _LegacyConfigCenter
except ImportError:
    # 如果原文件不存在，使用新的实现
    _LegacyConfigCenter = ConfigCenter

__all__ = [
    'get_app_config_manager',
    'get_config_manager', 
    'ConfigCenter',
    'ConfigManager',
    'AppConfigManager'
]