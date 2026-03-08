#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频状态管理器
协调VAD（语音活动检测）和TTS（文本转语音）的状态，实现AI打断功能
"""

from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional
from loguru import logger
from OQConfig.app_settings_manager import get_app_settings_manager


class AudioStateManager(QObject):
    """音频状态管理器 - 协调VAD和TTS状态"""
    
    # 定义信号
    ai_speech_started = pyqtSignal()  # AI开始说话
    ai_speech_finished = pyqtSignal()  # AI说话结束
    user_interrupt_detected = pyqtSignal()  # 检测到用户打断
    vad_pause_requested = pyqtSignal()  # VAD暂停请求
    vad_resume_requested = pyqtSignal()  # VAD恢复请求
    tts_should_stop = pyqtSignal()  # TTS应该停止
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 获取应用设置管理器
        self.app_settings = get_app_settings_manager()
        
        # 状态变量
        self.is_ai_speaking = False  # AI是否正在说话
        self.is_vad_active = False  # VAD是否激活
        self.is_user_speaking = False  # 用户是否正在说话
        self.vad_paused_by_ai = False  # VAD是否因AI说话而暂停
        
        # TTS管理器引用
        self.sync_tts_manager = None
        
        logger.info("[AudioState] 音频状态管理器初始化完成")
    
    def set_sync_tts_manager(self, sync_tts_manager):
        """设置TTS管理器引用"""
        self.sync_tts_manager = sync_tts_manager
        
        if sync_tts_manager:
            # 连接TTS播放信号
            sync_tts_manager.audio_playback_started.connect(self.on_ai_speech_started)
            sync_tts_manager.audio_playback_finished.connect(self.on_ai_speech_finished)
            logger.info("[AudioState] 已连接TTS管理器信号")
    
    def on_ai_speech_started(self):
        """AI开始说话"""
        self.is_ai_speaking = True
        self.ai_speech_started.emit()
        logger.info("[AudioState] AI开始说话")
        
        # 根据设置决定是否暂停VAD
        if not self.app_settings.is_ai_interrupt_enabled():
            # 如果不允许打断，暂停VAD
            if self.is_vad_active:
                self.vad_paused_by_ai = True
                self.vad_pause_requested.emit()
                logger.info("[AudioState] AI说话期间暂停VAD（不允许打断）")
        else:
            # 如果允许打断，保持VAD激活
            logger.info("[AudioState] AI说话期间保持VAD激活（允许打断）")
    
    def on_ai_speech_finished(self):
        """AI说话结束"""
        self.is_ai_speaking = False
        self.ai_speech_finished.emit()
        logger.info("[AudioState] AI说话结束")
        
        # 如果VAD因AI说话而暂停，现在恢复它
        if self.vad_paused_by_ai:
            self.vad_paused_by_ai = False
            if self.is_vad_active:
                self.vad_resume_requested.emit()
                logger.info("[AudioState] AI说话结束，恢复VAD")
    
    def on_vad_activated(self):
        """VAD被激活"""
        self.is_vad_active = True
        logger.info("[AudioState] VAD已激活")
        
        # 如果AI正在说话且不允许打断，立即暂停VAD
        if self.is_ai_speaking and not self.app_settings.is_ai_interrupt_enabled():
            self.vad_paused_by_ai = True
            self.vad_pause_requested.emit()
            logger.info("[AudioState] VAD激活时AI正在说话，立即暂停VAD")
    
    def on_vad_deactivated(self):
        """VAD被停用"""
        self.is_vad_active = False
        self.vad_paused_by_ai = False
        logger.info("[AudioState] VAD已停用")
    
    def on_user_speech_detected(self):
        """检测到用户语音"""
        self.is_user_speaking = True
        logger.info("[AudioState] 检测到用户语音")
    
    def on_user_speech_finished(self):
        """用户语音结束"""
        self.is_user_speaking = False
        logger.info("[AudioState] 用户语音结束")
    
    def can_start_recording(self) -> bool:
        """判断是否可以开始录音"""
        # 如果AI正在说话且不允许打断，则不能开始录音
        if self.is_ai_speaking and not self.app_settings.is_ai_interrupt_enabled():
            return False
        
        # 其他情况下允许录音
        return True
    
    def is_ai_interrupt_enabled(self) -> bool:
        """检查是否启用了AI打断功能"""
        return self.app_settings.is_ai_interrupt_enabled()
    
    def on_user_interrupt_detected(self):
        """用户打断AI说话"""
        if self.is_ai_speaking and self.app_settings.is_ai_interrupt_enabled():
            self.user_interrupt_detected.emit()
            self.tts_should_stop.emit()
            logger.info("[AudioState] 用户打断AI说话，停止TTS")
    
    def should_allow_vad(self) -> bool:
        """判断是否应该允许VAD工作"""
        if not self.is_vad_active:
            return False
        
        # 如果AI正在说话
        if self.is_ai_speaking:
            # 根据设置决定是否允许VAD
            return self.app_settings.is_ai_interrupt_enabled()
        
        # AI没有说话时，允许VAD
        return True
    
    def get_state_info(self) -> dict:
        """获取当前状态信息"""
        return {
            "is_ai_speaking": self.is_ai_speaking,
            "is_vad_active": self.is_vad_active,
            "is_user_speaking": self.is_user_speaking,
            "vad_paused_by_ai": self.vad_paused_by_ai,
            "ai_interrupt_enabled": self.app_settings.is_ai_interrupt_enabled(),
            "should_allow_vad": self.should_allow_vad()
        }


# 全局音频状态管理器实例
_audio_state_manager = None

def get_audio_state_manager() -> AudioStateManager:
    """获取全局音频状态管理器实例"""
    global _audio_state_manager
    if _audio_state_manager is None:
        _audio_state_manager = AudioStateManager()
    return _audio_state_manager