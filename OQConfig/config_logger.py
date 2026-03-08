#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置同步日志记录器
提供详细的日志记录和错误处理功能
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class ConfigLogger:
    """配置同步专用日志记录器"""
    
    def __init__(self, log_dir: str = None, log_level: int = logging.INFO):
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # 创建日志文件路径
        log_filename = f"config_sync_{datetime.now().strftime('%Y%m%d')}.log"
        self.log_file = self.log_dir / log_filename
        
        # 配置日志记录器
        self.logger = logging.getLogger("ConfigSync")
        self.logger.setLevel(log_level)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """设置日志处理器"""
        # 文件处理器
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 统一文件日志格式为 HH:MM:SS | LEVEL | [ConfigSync] message
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | [ConfigSync] %(message)s',
            datefmt='%H:%M:%S'
        )

        file_handler.setFormatter(formatter)

        # 仅写入文件，控制台输出交由入口的 loguru 统一处理
        self.logger.addHandler(file_handler)
        self.logger.propagate = True
    
    def info(self, message: str, extra_data: dict = None):
        """记录信息日志"""
        log_msg = self._format_message(message, extra_data)
        self.logger.info(log_msg)
    
    def warning(self, message: str, extra_data: dict = None):
        """记录警告日志"""
        log_msg = self._format_message(message, extra_data)
        self.logger.warning(log_msg)
    
    def error(self, message: str, exception: Exception = None, extra_data: dict = None):
        """记录错误日志"""
        log_msg = self._format_message(message, extra_data)
        if exception:
            log_msg += f" | 异常: {type(exception).__name__}: {str(exception)}"
        self.logger.error(log_msg)
    
    def debug(self, message: str, extra_data: dict = None):
        """记录调试日志"""
        log_msg = self._format_message(message, extra_data)
        self.logger.debug(log_msg)
    
    def sync_start(self, config_type: str, source: str, old_value: str = None, new_value: str = None):
        """记录同步开始"""
        extra_data = {
            "config_type": config_type,
            "source": source,
            "old_value_length": len(old_value) if old_value else 0,
            "new_value_length": len(new_value) if new_value else 0
        }
        self.info(f"开始同步 {config_type}", extra_data)
    
    def sync_success(self, config_type: str, source: str, duration_ms: float = None):
        """记录同步成功"""
        extra_data = {
            "config_type": config_type,
            "source": source,
            "duration_ms": duration_ms
        }
        self.info(f"✅ {config_type} 同步成功", extra_data)
    
    def sync_failure(self, config_type: str, source: str, error_message: str, exception: Exception = None):
        """记录同步失败"""
        extra_data = {
            "config_type": config_type,
            "source": source,
            "error_message": error_message
        }
        self.error(f"❌ {config_type} 同步失败", exception, extra_data)
    
    def config_validation_error(self, config_type: str, validation_error: str):
        """记录配置验证错误"""
        extra_data = {
            "config_type": config_type,
            "validation_error": validation_error
        }
        self.error(f"配置验证失败: {config_type}", extra_data=extra_data)
    
    def file_operation_error(self, operation: str, file_path: str, exception: Exception):
        """记录文件操作错误"""
        extra_data = {
            "operation": operation,
            "file_path": file_path
        }
        self.error(f"文件操作失败: {operation}", exception, extra_data)
    
    def _format_message(self, message: str, extra_data: dict = None) -> str:
        """格式化日志消息"""
        if not extra_data:
            return message
        
        extra_str = " | ".join([f"{k}={v}" for k, v in extra_data.items() if v is not None])
        return f"{message} | {extra_str}" if extra_str else message
    
    def get_log_file_path(self) -> str:
        """获取日志文件路径"""
        return str(self.log_file)
    
    def get_recent_logs(self, lines: int = 50) -> list:
        """获取最近的日志记录"""
        try:
            if not self.log_file.exists():
                return []
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception as e:
            self.error("读取日志文件失败", e)
            return []
    
    def clear_old_logs(self, days_to_keep: int = 7):
        """清理旧日志文件"""
        try:
            current_time = datetime.now()
            for log_file in self.log_dir.glob("config_sync_*.log"):
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if (current_time - file_time).days > days_to_keep:
                    log_file.unlink()
                    self.info(f"已删除旧日志文件: {log_file.name}")
        except Exception as e:
            self.error("清理旧日志文件失败", e)


# 全局日志记录器实例
_config_logger = None


def get_config_logger() -> ConfigLogger:
    """获取全局配置日志记录器实例"""
    global _config_logger
    if _config_logger is None:
        # 尝试在项目根目录创建logs文件夹
        try:
            project_root = Path(__file__).parent.parent
            log_dir = project_root / "logs"
            _config_logger = ConfigLogger(str(log_dir))
        except Exception:
            # 如果失败，使用当前目录
            _config_logger = ConfigLogger()
    return _config_logger


# 便捷函数
def log_info(message: str, **kwargs):
    """便捷函数：记录信息日志"""
    get_config_logger().info(message, kwargs)


def log_warning(message: str, **kwargs):
    """便捷函数：记录警告日志"""
    get_config_logger().warning(message, kwargs)


def log_error(message: str, exception: Exception = None, **kwargs):
    """便捷函数：记录错误日志"""
    get_config_logger().error(message, exception, kwargs)


def log_debug(message: str, **kwargs):
    """便捷函数：记录调试日志"""
    get_config_logger().debug(message, kwargs)