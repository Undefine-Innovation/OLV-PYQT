from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import os
import yaml
from loguru import logger

# 导入应用设置管理器
from OQConfig.app_settings_manager import get_app_settings_manager

# 导入配置管理器和同步服务
try:
    from OQConfig.config_manager import get_config_manager
    from OQConfig.config_sync_service import get_config_sync_service
    config_manager = get_config_manager()
    config_sync_service = get_config_sync_service()
except ImportError as e:
    logger.warning(f"警告: 无法导入配置管理器或同步服务: {e}")
    config_manager = None
    config_sync_service = None


class SettingsQmlSlot(QObject):
    """设置页面的槽函数类 - 简化版，只打印日志"""
    
    # 定义信号
    backToMainRequested = pyqtSignal()
    settingsSaved = pyqtSignal(str)  # 发送保存成功的消息
    settingsError = pyqtSignal(str)  # 发送错误消息
    
    # 窗口设置相关信号
    windowModeChanged = pyqtSignal(int)  # 窗口模式改变
    windowSettingsSaved = pyqtSignal(str)  # 窗口设置保存
    
    # 模型设置相关信号
    modelFileSelected = pyqtSignal(str)  # 模型文件选择
    modelPathChanged = pyqtSignal(str)  # 模型路径改变
    modelSettingsSaved = pyqtSignal(str)  # 模型设置保存
    
    # 角色设置相关信号（保留兼容性）
    roleFileSelected = pyqtSignal(str)  # 角色文件选择
    rolePathChanged = pyqtSignal(str)  # 角色路径改变
    roleSettingsSaved = pyqtSignal(str)  # 角色设置保存
    
    # 背景设置相关信号
    backgroundTypeChanged = pyqtSignal(int)  # 背景类型改变
    backgroundThemeChanged = pyqtSignal(int)  # 背景主题改变
    wallpaperFileSelected = pyqtSignal(str)  # 壁纸文件选择
    wallpaperPathChanged = pyqtSignal(str)  # 壁纸路径改变
    backgroundSettingsSaved = pyqtSignal(str)  # 背景设置保存
    
    # ASR设置相关信号
    asrProviderChanged = pyqtSignal(int)  # ASR提供商改变
    asrApiKeyChanged = pyqtSignal(str)  # ASR API密钥改变
    asrModelPathChanged = pyqtSignal(str)  # ASR模型路径改变
    asrSettingsSaved = pyqtSignal(str)  # ASR设置保存
    
    # TTS设置相关信号
    ttsProviderChanged = pyqtSignal(int)  # TTS提供商改变
    ttsVoiceChanged = pyqtSignal(str)  # TTS语音改变
    ttsApiKeyChanged = pyqtSignal(str)  # TTS API密钥改变
    ttsModelPathChanged = pyqtSignal(str)  # TTS模型路径改变
    ttsSpeedChanged = pyqtSignal(float)  # TTS语速改变
    ttsVolumeChanged = pyqtSignal(float)  # TTS音量改变
    ttsSettingsSaved = pyqtSignal(str)  # TTS设置保存
    

    
    # 助理设置相关信号
    assistantNameChanged = pyqtSignal(str)  # 助理名称改变
    assistantPersonalityChanged = pyqtSignal(str)  # 助理性格改变
    systemPromptChanged = pyqtSignal(str)  # 系统提示词改变
    memoryEnabledChanged = pyqtSignal(bool)  # 记忆功能启用状态改变
    contextLengthChanged = pyqtSignal(int)  # 上下文长度改变
    assistantSettingsSaved = pyqtSignal(str)  # 助理设置保存
    
    # 其他功能信号
    connectionTested = pyqtSignal(str)  # 连接测试结果
    settingsReset = pyqtSignal(str)  # 设置重置结果
    configRequested = pyqtSignal(str)  # 配置请求结果
    
    # 配置同步相关信号
    configSyncSuccess = pyqtSignal(str)  # 配置同步成功
    configSyncFailed = pyqtSignal(str)  # 配置同步失败
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化应用设置管理器
        self.app_settings = get_app_settings_manager()
        
        # 连接设置变化信号
        self.app_settings.settingChanged.connect(self.on_app_setting_changed)
        
        logger.info("[Settings] 设置槽函数初始化完成")
    
    def on_app_setting_changed(self, setting_name: str, value):
        """处理应用设置变化"""
        logger.info(f"[Settings] 应用设置变化: {setting_name} = {value}")
        
        # 根据设置名称执行相应的逻辑
        if setting_name == "ai_interrupt_enabled":
            self.handle_ai_interrupt_setting_changed(value)
        elif setting_name == "mute_on_ai_talk":
            self.handle_mute_on_ai_talk_changed(value)
        elif setting_name == "unmute_on_chat_end":
            self.handle_unmute_on_chat_end_changed(value)
    
    def handle_ai_interrupt_setting_changed(self, enabled: bool):
        """处理AI打断设置变化"""
        logger.info(f"[Settings] AI打断功能{'启用' if enabled else '禁用'}")
        # 这里可以添加通知其他组件的逻辑
        # 例如通知VAD系统、TTS系统等
    
    def handle_mute_on_ai_talk_changed(self, enabled: bool):
        """处理AI说话时静音设置变化"""
        logger.info(f"[Settings] AI说话时静音功能{'启用' if enabled else '禁用'}")
    
    def handle_unmute_on_chat_end_changed(self, enabled: bool):
        """处理聊天结束时取消静音设置变化"""
        logger.info(f"[Settings] 聊天结束时取消静音功能{'启用' if enabled else '禁用'}")
    
    @pyqtSlot()
    def onBackToMain(self):
        """返回主页面槽函数"""
        logger.info("[Settings] 返回主页面按钮被点击")
        self.backToMainRequested.emit()
    
    @pyqtSlot(int)
    def onWindowModeChanged(self, mode_index):
        """窗口模式改变槽函数"""
        mode_names = ["沉浸模式", "窗口模式", "桌宠模式"]
        if 0 <= mode_index < len(mode_names):
            logger.info(f"[Settings] 窗口模式改变: {mode_names[mode_index]} (索引: {mode_index})")
            self.windowModeChanged.emit(mode_index)
        else:
            logger.warning(f"[Settings] 无效的窗口模式索引: {mode_index}")
    
    @pyqtSlot()
    def onSaveWindowSettings(self):
        """保存窗口设置槽函数"""
        logger.info("[Settings] 保存窗口设置按钮被点击")
        self.windowSettingsSaved.emit("窗口设置已记录到日志")
        self.settingsSaved.emit("窗口设置已记录到日志")
    
    @pyqtSlot(result=str)
    def onBrowseRoleFile(self):
        """浏览角色文件槽函数"""
        logger.info("[Settings] 浏览角色文件按钮被点击")
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择角色文件",
            "",
            "模型文件 (*.json *.model3);;所有文件 (*)"
        )
        if file_path:
            logger.info(f"[Settings] 选择的角色文件: {file_path}")
            self.roleFileSelected.emit(file_path)
        else:
            logger.warning("[Settings] 取消选择角色文件")
        return file_path if file_path else ""
    
    @pyqtSlot(str)
    def onRolePathChanged(self, role_path):
        """角色路径改变槽函数"""
        logger.info(f"[Settings] 角色路径改变: {role_path}")
        self.rolePathChanged.emit(role_path)
    
    @pyqtSlot()
    def onSaveRoleSettings(self):
        """保存角色设置槽函数"""
        logger.info("[Settings] 保存角色设置按钮被点击")
        self.roleSettingsSaved.emit("角色设置已记录到日志")
        self.settingsSaved.emit("角色设置已记录到日志")
    
    @pyqtSlot(int)
    def onBackgroundTypeChanged(self, bg_type):
        """背景类型改变槽函数"""
        bg_types = ["默认壁纸", "自定义壁纸"]
        if 0 <= bg_type < len(bg_types):
            logger.info(f"[Settings] 背景类型改变: {bg_types[bg_type]} (索引: {bg_type})")
            self.backgroundTypeChanged.emit(bg_type)
        else:
            logger.warning(f"[Settings] 无效的背景类型索引: {bg_type}")
    
    @pyqtSlot(int)
    def onBackgroundThemeChanged(self, theme_index):
        """背景主题改变槽函数"""
        themes = ["默认背景", "深色主题", "月亮主题", "科技寝室", "绿色自然", "城市房间", "教室场景", "室内场景", "山谷风景"]
        if 0 <= theme_index < len(themes):
            logger.info(f"[Settings] 背景主题改变: {themes[theme_index]} (索引: {theme_index})")
            self.backgroundThemeChanged.emit(theme_index)
        else:
            logger.warning(f"[Settings] 无效的背景主题索引: {theme_index}")
    
    @pyqtSlot(result=str)
    def onBrowseWallpaper(self):
        """浏览壁纸文件槽函数"""
        logger.info("[Settings] 浏览壁纸文件按钮被点击")
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择壁纸文件",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*)"
        )
        if file_path:
            logger.info(f"[Settings] 选择的壁纸文件: {file_path}")
            self.wallpaperFileSelected.emit(file_path)
        else:
            logger.warning("[Settings] 取消选择壁纸文件")
        return file_path if file_path else ""
    
    @pyqtSlot(str)
    def onWallpaperPathChanged(self, wallpaper_path):
        """壁纸路径改变槽函数"""
        logger.info(f"[Settings] 壁纸路径改变: {wallpaper_path}")
        self.wallpaperPathChanged.emit(wallpaper_path)
    
    @pyqtSlot()
    def onSaveBackgroundSettings(self):
        """保存背景设置槽函数"""
        logger.info("[Settings] 保存背景设置按钮被点击")
        self.backgroundSettingsSaved.emit("背景设置已记录到日志")
        self.settingsSaved.emit("背景设置已记录到日志")
    
    @pyqtSlot(int)
    def onAsrProviderChanged(self, provider_index):
        """ASR提供商改变槽函数"""
        providers = ["OpenAI Whisper", "Azure", "Faster Whisper", "Sherpa ONNX", "Groq Whisper", "Fun ASR", "Whisper CPP"]
        if 0 <= provider_index < len(providers):
            logger.info(f"[Settings] ASR提供商改变: {providers[provider_index]} (索引: {provider_index})")
        else:
            logger.warning(f"[Settings] 无效的ASR提供商索引: {provider_index}")
    
    @pyqtSlot(str)
    def onAsrApiKeyChanged(self, api_key):
        """ASR API密钥改变槽函数"""
        # 为了安全，只显示前几位字符
        masked_key = api_key[:8] + "..." if len(api_key) > 8 else api_key
        logger.info(f"[Settings] ASR API密钥改变: {masked_key}")
    
    @pyqtSlot(str)
    def onAsrModelPathChanged(self, model_path):
        """ASR模型路径改变槽函数"""
        logger.info(f"[Settings] ASR模型路径改变: {model_path}")
    
    @pyqtSlot()
    def onSaveAsrSettings(self):
        """保存ASR设置槽函数"""
        logger.info("[Settings] 保存ASR设置按钮被点击")
        self.settingsSaved.emit("ASR设置已记录到日志")
    
    # 添加缺失的ASR相关槽函数
    @pyqtSlot(bool)
    def onMuteOnAiTalkChanged(self, checked):
        """AI说话时静音槽函数"""
        logger.info(f"[Settings] AI说话时静音设置改变: {'启用' if checked else '禁用'}")
        # 保存设置到应用设置管理器
        self.app_settings.set_mute_on_ai_talk(checked)
    
    @pyqtSlot(bool)
    def onUnmuteOnChatEndChanged(self, checked):
        """聊天结束时取消静音槽函数"""
        logger.info(f"[Settings] 聊天结束时取消静音设置改变: {'启用' if checked else '禁用'}")
        # 保存设置到应用设置管理器
        self.app_settings.set_unmute_on_chat_end(checked)
    
    @pyqtSlot(bool)
    def onInterruptAiChanged(self, checked):
        """允许打断AI槽函数"""
        logger.info(f"[Settings] 允许打断AI设置改变: {'启用' if checked else '禁用'}")
        # 保存设置到应用设置管理器
        self.app_settings.set_ai_interrupt_enabled(checked)
    
    @pyqtSlot(result=bool)
    def getAiInterruptEnabled(self):
        """获取AI打断设置状态"""
        enabled = self.app_settings.is_ai_interrupt_enabled()
        logger.info(f"[Settings] 获取AI打断设置状态: {'启用' if enabled else '禁用'}")
        return enabled
    
    @pyqtSlot(result=bool)
    def getMuteOnAiTalk(self):
        """获取AI说话时静音设置状态"""
        enabled = self.app_settings.is_mute_on_ai_talk()
        logger.info(f"[Settings] 获取AI说话时静音设置状态: {'启用' if enabled else '禁用'}")
        return enabled
    
    @pyqtSlot(result=bool)
    def getUnmuteOnChatEnd(self):
        """获取聊天结束时取消静音设置状态"""
        enabled = self.app_settings.is_unmute_on_chat_end()
        logger.info(f"[Settings] 获取聊天结束时取消静音设置状态: {'启用' if enabled else '禁用'}")
        return enabled
    
    @pyqtSlot(float)
    def onMicSensitivityChanged(self, value):
        """麦克风灵敏度改变槽函数"""
        # 将浮点数值转换为webrtcvad支持的整数模式(0-3)
        # 输入范围假设为0.0-1.0，映射到0-3
        vad_mode = int(value * 3)
        # 确保值在有效范围内
        vad_mode = max(0, min(3, vad_mode))
        
        logger.info(f"[Settings] 麦克风灵敏度改变: {value} -> VAD模式: {vad_mode}")
        
        # 发送信号通知VAD系统更新灵敏度
        from PyQt5.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if app:
            # 通过应用程序实例广播灵敏度变化事件
            app.vad_sensitivity_changed = vad_mode
    
    @pyqtSlot()
    def onTestMicrophone(self):
        """测试麦克风槽函数"""
        logger.info("[Settings] 测试麦克风按钮被点击")
    

    
    # 添加缺失的助理设置相关槽函数
    @pyqtSlot(bool)
    def onAutoReplyChanged(self, checked):
        """自动回复设置改变槽函数"""
        logger.info(f"[Settings] 自动回复设置改变: {'启用' if checked else '禁用'}")
    
    @pyqtSlot(int)
    def onReplyDelayChanged(self, value):
        """回复延迟设置改变槽函数"""
        logger.info(f"[Settings] 回复延迟设置改变: {value}秒")
    
    @pyqtSlot(str)
    def onAssistantPromptChanged(self, text):
        """助理提示词改变槽函数"""
        # 截断长文本以避免日志过长
        short_text = text[:50] + "..." if len(text) > 50 else text
        logger.info(f"[Settings] 助理提示词改变: {short_text}")
    
    @pyqtSlot(int)
    def onTtsProviderChanged(self, provider_index):
        """TTS提供商改变槽函数"""
        providers = ["Edge TTS", "Azure TTS", "Bark TTS", "Coqui TTS", "CosyVoice TTS", "Fish API TTS", "GPT-SoVITS TTS", "MeloTTS", "Sherpa ONNX TTS", "XTTS"]
        if 0 <= provider_index < len(providers):
            logger.info(f"[Settings] TTS提供商改变: {providers[provider_index]} (索引: {provider_index})")
        else:
            logger.warning(f"[Settings] 无效的TTS提供商索引: {provider_index}")
    
    @pyqtSlot(str)
    def onTtsVoiceChanged(self, voice):
        """TTS语音改变槽函数"""
        logger.info(f"[Settings] TTS语音改变: {voice}")
    
    @pyqtSlot(str)
    def onTtsApiKeyChanged(self, api_key):
        """TTS API密钥改变槽函数"""
        # 为了安全，只显示前几位字符
        masked_key = api_key[:8] + "..." if len(api_key) > 8 else api_key
        logger.info(f"[Settings] TTS API密钥改变: {masked_key}")
    
    @pyqtSlot(str)
    def onTtsModelPathChanged(self, model_path):
        """TTS模型路径改变槽函数"""
        logger.info(f"[Settings] TTS模型路径改变: {model_path}")
    
    @pyqtSlot(float)
    def onTtsSpeedChanged(self, speed):
        """TTS语速改变槽函数"""
        logger.info(f"[Settings] TTS语速改变: {speed}")
    
    @pyqtSlot(float)
    def onTtsVolumeChanged(self, volume):
        """TTS音量改变槽函数"""
        logger.info(f"[Settings] TTS音量改变: {volume}")
    
    @pyqtSlot()
    def onSaveTtsSettings(self):
        """保存TTS设置槽函数"""
        logger.info("[Settings] 保存TTS设置按钮被点击")
        self.settingsSaved.emit("TTS设置已记录到日志")
    

    
    @pyqtSlot(str)
    def onAssistantNameChanged(self, name):
        """助理名称改变槽函数"""
        logger.info(f"[Settings] 助理名称改变: {name}")
    
    @pyqtSlot(str)
    def onAssistantPersonalityChanged(self, personality):
        """助理性格改变槽函数"""
        logger.info(f"[Settings] 助理性格改变: {personality}")
    
    @pyqtSlot(bool)
    def onMemoryEnabledChanged(self, enabled):
        """记忆功能启用状态改变槽函数"""
        logger.info(f"[Settings] 记忆功能启用状态改变: {'启用' if enabled else '禁用'}")
    
    @pyqtSlot(int)
    def onContextLengthChanged(self, length):
        """上下文长度改变槽函数"""
        logger.info(f"[Settings] 上下文长度改变: {length}")
    
    @pyqtSlot()
    def onSaveAssistantSettings(self):
        """保存助理设置槽函数"""
        logger.info("[Settings] 保存助理设置按钮被点击")
        self.settingsSaved.emit("助理设置已记录到日志")
    
    @pyqtSlot()
    def onTestConnection(self):
        """测试连接槽函数"""
        logger.info("[Settings] 测试连接按钮被点击")
        self.connectionTested.emit("连接测试已执行（仅日志）")
        self.settingsSaved.emit("连接测试已执行（仅日志）")
    
    @pyqtSlot()
    def onResetToDefault(self):
        """重置为默认设置槽函数"""
        logger.info("[Settings] 重置为默认设置按钮被点击")
        self.settingsReset.emit("已重置为默认设置（仅日志）")
        self.settingsSaved.emit("已重置为默认设置（仅日志）")
    
    @pyqtSlot(result=str)
    def getCurrentConfig(self):
        """获取当前配置的JSON字符串"""
        logger.info("[Settings] 获取当前配置被调用")
        config_result = '{"message": "配置获取功能已简化为日志模式"}'
        self.configRequested.emit(config_result)
        return config_result
    
    # 模型设置相关方法
    @pyqtSlot(result=str)
    def onBrowseModelFile(self):
        """浏览模型文件槽函数"""
        logger.info("[Settings] 浏览模型文件按钮被点击")
        
        # 获取默认路径
        default_path = ""
        if config_manager:
            try:
                current_path = config_manager.get_character_path()
                if current_path and os.path.exists(os.path.dirname(current_path)):
                    default_path = os.path.dirname(current_path)
                else:
                    default_path = "resources/v3"
            except Exception as e:
                logger.error(f"[Settings] 获取默认路径失败: {e}")
                default_path = "resources/v3"
        
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择模型文件",
            default_path,
            "Live2D模型文件 (*.model3.json *.model.json);;所有文件 (*)"
        )
        
        if file_path:
            logger.info(f"[Settings] 选择的模型文件: {file_path}")
            self.modelFileSelected.emit(file_path)
            # 同时发送角色文件选择信号以保持兼容性
            self.roleFileSelected.emit(file_path)
        else:
            logger.warning("[Settings] 取消选择模型文件")
        
        return file_path if file_path else ""
    
    @pyqtSlot(str)
    def onModelPathChanged(self, model_path):
        """模型路径改变槽函数"""
        logger.info(f"[Settings] 模型路径改变: {model_path}")
        
        # 更新配置文件中的character_path
        if config_manager and model_path:
            try:
                success = config_manager.set_character_path(model_path)
                if success:
                    logger.success(f"[Settings] 已更新配置中的模型路径: {model_path}")
                    # 立即触发模型设置保存信号，实现热重载
                    message = f"模型路径已更新: {os.path.basename(model_path)}"
                    self.modelSettingsSaved.emit(message)
                else:
                    logger.error(f"[Settings] 更新配置中的模型路径失败: {model_path}")
            except Exception as e:
                logger.error(f"[Settings] 更新配置中的模型路径失败: {e}")
        
        self.modelPathChanged.emit(model_path)
        # 同时发送角色路径改变信号以保持兼容性
        self.rolePathChanged.emit(model_path)
    
    @pyqtSlot()
    def onSaveModelSettings(self):
        """保存模型设置槽函数"""
        logger.info("[Settings] 保存模型设置按钮被点击")
        
        # 获取当前选择的模型路径
        try:
            if config_manager:
                model_path = config_manager.get_character_path()
                if model_path and os.path.exists(model_path):
                    # 配置已经在onModelPathChanged中保存了，这里只需要确认
                    message = f"模型设置已保存: {os.path.basename(model_path)}"
                    logger.info(f"[Settings] {message}")
                    self.modelSettingsSaved.emit(message)
                    self.settingsSaved.emit(message)
                    # 同时发送角色设置保存信号以保持兼容性
                    self.roleSettingsSaved.emit(message)
                else:
                    error_msg = "请先选择有效的模型文件"
                    logger.error(f"[Settings] {error_msg}")
                    self.settingsError.emit(error_msg)
            else:
                error_msg = "配置管理器未初始化"
                logger.error(f"[Settings] {error_msg}")
                self.settingsError.emit(error_msg)
        except Exception as e:
            error_msg = f"保存模型设置时发生错误: {str(e)}"
            logger.error(f"[Settings] {error_msg}")
            self.settingsError.emit(error_msg)
    
    @pyqtSlot(str, result=str)
    def getConfigValue(self, key_path):
        """根据键路径获取配置值"""
        logger.info(f"[Settings] 获取配置值: {key_path}")
        return "日志模式"