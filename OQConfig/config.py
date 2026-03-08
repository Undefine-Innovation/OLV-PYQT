from typing import Dict, Any

# 导入简化的配置管理器
try:
    from .config_manager import get_config_manager
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from config_manager import get_config_manager


class ConfigCenter:
    """配置中心 - 提供统一的配置访问接口"""

    @classmethod
    def get_llm_config(cls, conf_uid: str) -> Dict[str, Any]:
        """获取LLM配置"""
        try:
            return get_config_manager().get_llm_config(conf_uid)
        except Exception as e:
            # 回退到传统方式
            configs = cls._load_config().get("llm_configs", {})
            if conf_uid not in configs:
                raise ValueError(f"Unsupported LLM type: {conf_uid}. Supported types: {list(configs.keys())}")
            return configs[conf_uid]

    @classmethod
    def get_agent_config(cls, conf_uid: str, conf_llm_type: str) -> Dict[str, Any]:
        """获取Agent配置"""
        try:
            return get_config_manager().get_agent_config(conf_llm_type)
        except Exception as e:
            raise RuntimeError(f"Failed to get agent config: {e}")

    @classmethod
    def get_asr_config(cls, conf_uid: str) -> Dict[str, Any]:
        """获取ASR配置"""
        try:
            return get_config_manager().get_asr_config(conf_uid)
        except Exception as e:
            raise RuntimeError(f"Failed to get ASR config: {e}")

    @classmethod
    def get_tts_config(cls, conf_uid: str) -> Dict[str, Any]:
        """获取TTS配置"""
        try:
            return get_config_manager().get_tts_config(conf_uid)
        except Exception as e:
            raise RuntimeError(f"Failed to get TTS config: {e}")

    @classmethod
    def get_character_config(cls, character_name: str) -> Dict[str, Any]:
        """获取角色配置"""
        try:
            return get_config_manager().get_character_config(character_name)
        except Exception as e:
            raise RuntimeError(f"Failed to get character config: {e}")

    @classmethod
    def get_available_configs(cls) -> Dict[str, list]:
        """获取所有可用的配置列表"""
        try:
            return get_config_manager().get_available_configs()
        except Exception as e:
            return {
                "llm_configs": ["openai_llm", "claude_llm"],
                "asr_configs": ["openai_whisper", "azure_asr"],
                "tts_configs": ["edge_tts", "azure_tts"],
                "characters": ["default", "assistant"]
            }

    @classmethod
    def reload_config(cls):
        """重新加载配置"""
        get_config_manager().reload_config()
