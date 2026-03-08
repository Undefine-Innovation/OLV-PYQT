"""
QML设置页面组件
独立的QML设置页面类，用于处理应用程序的各种设置
"""

import os
from PyQt5.QtCore import QUrl
from PyQt5.QtQuickWidgets import QQuickWidget
from loguru import logger


class QMLSettingsPage(QQuickWidget):
    """QML设置页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent  # 保存父窗口引用
        self.setResizeMode(QQuickWidget.SizeRootObjectToView)
        
        # 创建槽函数对象
        from OQSettings.settings_qml_slot import SettingsQmlSlot
        self.settings_slot = SettingsQmlSlot(self)
        
        # 将槽函数对象注册到QML上下文中
        self.rootContext().setContextProperty("settingsSlot", self.settings_slot)
        
        # 添加错误处理
        # 获取脚本所在目录的绝对路径
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # 使用 os.path.join 拼接路径，确保跨平台兼容性
        qml_file = os.path.join(script_dir, "..", "OQSettings", "setting.qml")

        # 转换为绝对路径，避免相对路径问题
        qml_file = os.path.abspath(qml_file)

        # 检查文件是否存在
        if not os.path.exists(qml_file):
            raise FileNotFoundError(f"QML file not found: {qml_file}")

        logger.info(f"QML file path: {qml_file}")
            
        self.setSource(QUrl.fromLocalFile(qml_file))
        
        # 检查加载状态
        if self.status() == QQuickWidget.Error:
            logger.error("QML加载失败")
            for error in self.errors():
                logger.error(f"错误: {error.toString()}")
        else:
            # QML加载成功后连接信号
            self.connect_signals()
    
    def connect_signals(self):
        """连接QML信号"""
        root_object = self.rootObject()
        if root_object:
            # 连接返回信号
            root_object.backToMain.connect(self.back_to_main)
            logger.info("信号连接成功")
            
            # 连接槽函数对象的所有信号
            self.settings_slot.backToMainRequested.connect(self.back_to_main)
            self.settings_slot.settingsSaved.connect(self.on_settings_saved)
            self.settings_slot.settingsError.connect(self.on_settings_error)
            
            # 连接窗口设置信号
            self.settings_slot.windowModeChanged.connect(self.on_window_mode_changed)
            self.settings_slot.windowSettingsSaved.connect(self.on_window_settings_saved)
            
            # 连接角色设置信号
            self.settings_slot.roleFileSelected.connect(self.on_role_file_selected)
            self.settings_slot.rolePathChanged.connect(self.on_role_path_changed)
            self.settings_slot.roleSettingsSaved.connect(self.on_role_settings_saved)
            
            # 连接背景设置信号
            self.settings_slot.backgroundTypeChanged.connect(self.on_background_type_changed)
            self.settings_slot.backgroundThemeChanged.connect(self.on_background_theme_changed)
            self.settings_slot.wallpaperFileSelected.connect(self.on_wallpaper_file_selected)
            self.settings_slot.wallpaperPathChanged.connect(self.on_wallpaper_path_changed)
            self.settings_slot.backgroundSettingsSaved.connect(self.on_background_settings_saved)
            
            # 连接ASR设置信号
            self.settings_slot.asrProviderChanged.connect(self.on_asr_provider_changed)
            self.settings_slot.asrApiKeyChanged.connect(self.on_asr_api_key_changed)
            self.settings_slot.asrModelPathChanged.connect(self.on_asr_model_path_changed)
            self.settings_slot.asrSettingsSaved.connect(self.on_asr_settings_saved)
            
            # 连接TTS设置信号
            self.settings_slot.ttsProviderChanged.connect(self.on_tts_provider_changed)
            self.settings_slot.ttsVoiceChanged.connect(self.on_tts_voice_changed)
            self.settings_slot.ttsApiKeyChanged.connect(self.on_tts_api_key_changed)
            self.settings_slot.ttsModelPathChanged.connect(self.on_tts_model_path_changed)
            self.settings_slot.ttsSpeedChanged.connect(self.on_tts_speed_changed)
            self.settings_slot.ttsVolumeChanged.connect(self.on_tts_volume_changed)
            self.settings_slot.ttsSettingsSaved.connect(self.on_tts_settings_saved)
            

            
            # 连接助理设置信号
            self.settings_slot.assistantNameChanged.connect(self.on_assistant_name_changed)
            self.settings_slot.assistantPersonalityChanged.connect(self.on_assistant_personality_changed)
            self.settings_slot.systemPromptChanged.connect(self.on_system_prompt_changed)
            self.settings_slot.memoryEnabledChanged.connect(self.on_memory_enabled_changed)
            self.settings_slot.contextLengthChanged.connect(self.on_context_length_changed)
            self.settings_slot.assistantSettingsSaved.connect(self.on_assistant_settings_saved)
            
            # 连接其他功能信号
            self.settings_slot.connectionTested.connect(self.on_connection_tested)
            self.settings_slot.settingsReset.connect(self.on_settings_reset)
            self.settings_slot.configRequested.connect(self.on_config_requested)
            
            logger.info("所有槽函数信号连接成功")
            
        else:
            logger.error("无法获取根对象")
    
    def back_to_main(self):
        """返回主页面"""
        logger.info("返回按钮被点击")
        try:
            if self.parent_window:
                # 修复：使用 stacked_widget.setCurrentIndex 而不是直接调用 setCurrentIndex
                self.parent_window.stacked_widget.setCurrentIndex(0)
                # 添加延迟和异常处理来恢复Live2D渲染
                try:
                    if hasattr(self.parent_window, 'live2d_page') and self.parent_window.live2d_page:
                        # 使用QTimer延迟调用，避免立即渲染冲突
                        from PyQt5.QtCore import QTimer
                        QTimer.singleShot(100, self.parent_window.live2d_page.start_rendering)
                except Exception as e:
                    logger.error(f"恢复Live2D渲染时出错: {e}")
            else:
                logger.error("父窗口引用为空")
        except Exception as e:
            logger.error(f"返回主页面时出错: {e}")
            
    def on_settings_saved(self, message):
        """设置保存成功"""
        logger.info(f"设置操作成功: {message}")
        
    def on_settings_error(self, message):
        """设置保存失败"""
        logger.error(f"设置操作失败: {message}")
        # 这里可以显示错误提示
    
    def on_window_settings_saved(self, message):
        """处理窗口设置保存信号"""
        logger.info(f"窗口设置操作: {message}")
        # 这里可以根据需要添加特定的窗口设置处理逻辑
        # 比如切换窗口模式、调整窗口大小等
    
    def on_window_mode_changed(self, mode_index):
        """处理窗口模式改变"""
        logger.info(f"主窗口收到窗口模式改变信号: {mode_index}")
        # 这里可以添加实际的窗口模式切换逻辑
    
    def on_window_settings_saved(self, message):
        """处理窗口设置保存"""
        logger.info(f"主窗口收到窗口设置保存信号: {message}")
    
    # 角色设置处理方法
    def on_role_file_selected(self, file_path):
        """处理角色文件选择"""
        logger.info(f"主窗口收到角色文件选择信号: {file_path}")
    
    def on_role_path_changed(self, role_path):
        """处理角色路径改变"""
        logger.info(f"主窗口收到角色路径改变信号: {role_path}")
    
    def on_role_settings_saved(self, message):
        """处理角色设置保存"""
        logger.info(f"主窗口收到角色设置保存信号: {message}")
    
    # 背景设置处理方法
    def on_background_type_changed(self, bg_type):
        """处理背景类型改变"""
        logger.info(f"主窗口收到背景类型改变信号: {bg_type}")
    
    def on_background_theme_changed(self, theme_index):
        """处理背景主题改变"""
        logger.info(f"主窗口收到背景主题改变信号: {theme_index}")
    
    def on_wallpaper_file_selected(self, file_path):
        """处理壁纸文件选择"""
        logger.info(f"主窗口收到壁纸文件选择信号: {file_path}")
    
    def on_wallpaper_path_changed(self, wallpaper_path):
        """处理壁纸路径改变"""
        logger.info(f"主窗口收到壁纸路径改变信号: {wallpaper_path}")
    
    def on_background_settings_saved(self, message):
        """处理背景设置保存"""
        logger.info(f"主窗口收到背景设置保存信号: {message}")
    
    # ASR设置处理方法
    def on_asr_provider_changed(self, provider_index):
        """处理ASR提供商改变"""
        logger.info(f"主窗口收到ASR提供商改变信号: {provider_index}")
    
    def on_asr_api_key_changed(self, api_key):
        """处理ASR API密钥改变"""
        logger.info(f"主窗口收到ASR API密钥改变信号: [已脱敏]")
    
    def on_asr_model_path_changed(self, model_path):
        """处理ASR模型路径改变"""
        logger.info(f"主窗口收到ASR模型路径改变信号: {model_path}")
    
    def on_asr_settings_saved(self, message):
        """处理ASR设置保存"""
        logger.info(f"主窗口收到ASR设置保存信号: {message}")
    
    # TTS设置处理方法
    def on_tts_provider_changed(self, provider_index):
        """处理TTS提供商改变"""
        logger.info(f"主窗口收到TTS提供商改变信号: {provider_index}")
    
    def on_tts_voice_changed(self, voice):
        """处理TTS语音改变"""
        logger.info(f"主窗口收到TTS语音改变信号: {voice}")
    
    def on_tts_api_key_changed(self, api_key):
        """处理TTS API密钥改变"""
        logger.info(f"主窗口收到TTS API密钥改变信号: [已脱敏]")
    
    def on_tts_model_path_changed(self, model_path):
        """处理TTS模型路径改变"""
        logger.info(f"主窗口收到TTS模型路径改变信号: {model_path}")
    
    def on_tts_speed_changed(self, speed):
        """处理TTS语速改变"""
        logger.info(f"主窗口收到TTS语速改变信号: {speed}")
    
    def on_tts_volume_changed(self, volume):
        """处理TTS音量改变"""
        logger.info(f"主窗口收到TTS音量改变信号: {volume}")
    
    def on_tts_settings_saved(self, message):
        """处理TTS设置保存"""
        logger.info(f"主窗口收到TTS设置保存信号: {message}")
    

    
    # 助理设置处理方法
    def on_assistant_name_changed(self, name):
        """处理助理名称改变"""
        logger.info(f"主窗口收到助理名称改变信号: {name}")
    
    def on_assistant_personality_changed(self, personality):
        """处理助理性格改变"""
        logger.info(f"主窗口收到助理性格改变信号: {personality}")
    
    def on_system_prompt_changed(self, prompt):
        """处理系统提示词改变"""
        logger.info(f"主窗口收到系统提示词改变信号: [已截断]")
    
    def on_memory_enabled_changed(self, enabled):
        """处理记忆功能启用状态改变"""
        logger.info(f"主窗口收到记忆功能启用状态改变信号: {enabled}")
    
    def on_context_length_changed(self, length):
        """处理上下文长度改变"""
        logger.info(f"主窗口收到上下文长度改变信号: {length}")
    
    def on_assistant_settings_saved(self, message):
        """处理助理设置保存"""
        logger.info(f"主窗口收到助理设置保存信号: {message}")
    
    # 其他功能处理方法
    def on_connection_tested(self, result):
        """处理连接测试结果"""
        logger.info(f"主窗口收到连接测试结果信号: {result}")
    
    def on_settings_reset(self, result):
        """处理设置重置结果"""
        logger.info(f"主窗口收到设置重置结果信号: {result}")
    
    def on_config_requested(self, config):
        """处理配置请求结果"""
        logger.info(f"主窗口收到配置请求结果信号: {config}")