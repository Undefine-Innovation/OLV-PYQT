#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一配置管理器
整合了原来的ConfigManager和AppConfigManager的所有功能
提供配置加载、选择、应用的完整解决方案
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from copy import deepcopy


class ConfigManager:
    """简化的配置管理器"""
    
    def __init__(self, config_dir: str = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录路径
        """
        # 获取当前文件所在目录
        current_dir = Path(__file__).parent
        self.config_dir = Path(config_dir) if config_dir else current_dir
        self.config_file = self.config_dir / "config.yaml"
        self.selection_file = self.config_dir / "current_selection.json"
        
        # 配置数据缓存
        self._config_data = None
        self._current_selection = None
        
        # 加载配置
        self.load_config()
        self.load_selection()
    
    def load_config(self) -> bool:
        """
        加载配置文件
        
        Returns:
            bool: 加载是否成功
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f)
                return True
            else:
                raise FileNotFoundError(f"配置文件不存在: {self.config_file}")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self._config_data = {}
            return False
    
    def load_selection(self) -> bool:
        """
        加载当前配置选择
        
        Returns:
            bool: 加载是否成功
        """
        try:
            if self.selection_file.exists():
                with open(self.selection_file, 'r', encoding='utf-8') as f:
                    self._current_selection = json.load(f)
            else:
                # 设置默认选择
                self._current_selection = {
                    "llm": "openai_llm",
                    "asr": "openai_whisper", 
                    "tts": "edge_tts",
                    "character": "default"
                }
                self.save_selection()
            return True
        except Exception as e:
            print(f"加载配置选择失败: {e}")
            self._current_selection = {
                "llm": None,
                "asr": None,
                "tts": None,
                "character": None
            }
            return False
    
    def save_selection(self) -> bool:
        """
        保存当前配置选择
        
        Returns:
            bool: 保存是否成功
        """
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.selection_file, 'w', encoding='utf-8') as f:
                json.dump(self._current_selection, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存配置选择失败: {e}")
            return False
    
    def get_config_section(self, section: str) -> Dict[str, Any]:
        """
        获取配置文件中的指定部分
        
        Args:
            section: 配置部分名称
            
        Returns:
            Dict[str, Any]: 配置数据
        """
        if self._config_data is None:
            self.load_config()
        
        return deepcopy(self._config_data.get(section, {}))
    
    def get_llm_config(self, llm_type: str) -> Dict[str, Any]:
        """
        获取指定LLM配置
        
        Args:
            llm_type: LLM类型
            
        Returns:
            Dict[str, Any]: LLM配置
        """
        llm_configs = self.get_config_section("llm_configs")
        if llm_type not in llm_configs:
            raise ValueError(f"不支持的LLM类型: {llm_type}")
        return llm_configs[llm_type]
    
    def get_asr_config(self, asr_type: str) -> Dict[str, Any]:
        """
        获取指定ASR配置
        
        Args:
            asr_type: ASR类型
            
        Returns:
            Dict[str, Any]: ASR配置
        """
        asr_configs = self.get_config_section("asr_configs")
        if asr_type not in asr_configs:
            raise ValueError(f"不支持的ASR类型: {asr_type}")
        return asr_configs[asr_type]
    
    def get_tts_config(self, tts_type: str) -> Dict[str, Any]:
        """
        获取指定TTS配置
        
        Args:
            tts_type: TTS类型
            
        Returns:
            Dict[str, Any]: TTS配置
        """
        tts_configs = self.get_config_section("tts_configs")
        if tts_type not in tts_configs:
            raise ValueError(f"不支持的TTS类型: {tts_type}")
        return tts_configs[tts_type]
    
    def get_character_config(self, character_name: str) -> Dict[str, Any]:
        """
        获取指定角色配置
        
        Args:
            character_name: 角色名称
            
        Returns:
            Dict[str, Any]: 角色配置
        """
        characters = self.get_config_section("characters")
        if character_name not in characters:
            raise ValueError(f"不支持的角色: {character_name}")
        return characters[character_name]
    
    def get_agent_config(self, llm_type: str) -> Dict[str, Any]:
        """
        获取Agent配置
        
        Args:
            llm_type: LLM类型
            
        Returns:
            Dict[str, Any]: Agent配置
        """
        agent_template = self.get_config_section("agent_config_template")
        llm_config = self.get_llm_config(llm_type)
        
        # 合并配置
        agent_config = deepcopy(agent_template)
        
        # 为 AgentFactory.create_agent 构造正确的配置结构
        agent_config["llm_configs"] = {llm_type: llm_config}
        
        # 确保 agent_settings 中的 basic_memory_agent 包含 llm_provider
        if "agent_settings" in agent_config and "basic_memory_agent" in agent_config["agent_settings"]:
            agent_config["agent_settings"]["basic_memory_agent"]["llm_provider"] = llm_type
        
        return agent_config
    
    def get_current_selection(self) -> Dict[str, str]:
        """
        获取当前配置选择
        
        Returns:
            Dict[str, str]: 当前选择的配置
        """
        return deepcopy(self._current_selection)
    
    def set_current_config(self, config_type: str, config_name: str) -> bool:
        """
        设置当前使用的配置
        
        Args:
            config_type: 配置类型 (llm, asr, tts, character)
            config_name: 配置名称
            
        Returns:
            bool: 设置是否成功
        """
        if config_type not in ["llm", "asr", "tts", "character"]:
            return False
        
        # 验证配置是否存在
        try:
            if config_type == "llm":
                self.get_llm_config(config_name)
            elif config_type == "asr":
                self.get_asr_config(config_name)
            elif config_type == "tts":
                self.get_tts_config(config_name)
            elif config_type == "character":
                self.get_character_config(config_name)
        except ValueError:
            return False
        
        self._current_selection[config_type] = config_name
        return self.save_selection()
    
    def set_character_path(self, character_path: str) -> bool:
        """
        设置角色模型文件路径
        
        Args:
            character_path: 角色模型文件路径
            
        Returns:
            bool: 设置是否成功
        """
        if not character_path:
            return False
            
        # 验证文件是否存在
        if not os.path.exists(character_path):
            print(f"警告: 角色模型文件不存在: {character_path}")
            # 即使文件不存在也允许设置，可能是相对路径或稍后创建
        
        self._current_selection["character_path"] = character_path
        return self.save_selection()
    
    def get_character_path(self) -> Optional[str]:
        """
        获取当前设置的角色模型文件路径
        
        Returns:
            Optional[str]: 角色模型文件路径
        """
        return self._current_selection.get("character_path")
    
    def get_current_config(self, config_type: str) -> Optional[Dict[str, Any]]:
        """
        获取当前选择的配置
        
        Args:
            config_type: 配置类型
            
        Returns:
            Optional[Dict[str, Any]]: 当前配置数据
        """
        current_name = self._current_selection.get(config_type)
        if not current_name:
            return None
        
        try:
            if config_type == "llm":
                return self.get_llm_config(current_name)
            elif config_type == "asr":
                return self.get_asr_config(current_name)
            elif config_type == "tts":
                return self.get_tts_config(current_name)
            elif config_type == "character":
                return self.get_character_config(current_name)
            elif config_type == "agent":
                llm_name = self._current_selection.get("llm")
                if llm_name:
                    return self.get_agent_config(llm_name)
        except ValueError:
            return None
        
        return None
    
    def get_available_configs(self) -> Dict[str, list]:
        """
        获取所有可用的配置列表
        
        Returns:
            Dict[str, list]: 可用配置列表
        """
        return {
            "llm_configs": list(self.get_config_section("llm_configs").keys()),
            "asr_configs": list(self.get_config_section("asr_configs").keys()),
            "tts_configs": list(self.get_config_section("tts_configs").keys()),
            "characters": list(self.get_config_section("characters").keys()),
            "character_path": list(self.get_config_section("character_path").keys())
        }
    
    def get_available_llm_configs(self):
        """获取可用的LLM配置列表"""
        return list(self.get_config_section("llm_configs").keys())
    
    def get_available_asr_configs(self):
        """获取可用的ASR配置列表"""
        return list(self.get_config_section("asr_configs").keys())
    
    def get_available_tts_configs(self):
        """获取可用的TTS配置列表"""
        return list(self.get_config_section("tts_configs").keys())
    
    def get_available_characters(self):
        """获取可用的角色列表"""
        return list(self.get_config_section("characters").keys())

    def get_available_characters_path(self):
        return list(self.get_config_section("characters_path").keys())
    
    def get_current_llm_config(self):
        """获取当前LLM配置"""
        current_llm = self._current_selection.get('llm')
        if current_llm:
            return self.get_llm_config(current_llm)
        return None
    
    def get_current_asr_config(self):
        """获取当前ASR配置"""
        current_asr = self._current_selection.get('asr')
        if current_asr:
            return self.get_asr_config(current_asr)
        return None
    
    def get_current_tts_config(self):
        """获取当前TTS配置"""
        current_tts = self._current_selection.get('tts')
        if current_tts:
            return self.get_tts_config(current_tts)
        return None
    
    def reload_config(self):
        """
        重新加载配置文件
        """
        self._config_data = None
        self.load_config()
        self.load_selection()
    
    def save_config(self) -> bool:
        """
        保存配置文件到磁盘
        
        Returns:
            bool: 保存是否成功
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self._config_data, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def update_system_prompt(self, new_prompt: str) -> bool:
        """
        更新系统提示词到所有相关配置
        
        Args:
            new_prompt: 新的系统提示词
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 更新agent_config_template中的system_prompt
            if 'agent_config_template' in self._config_data:
                self._config_data['agent_config_template']['system_prompt'] = new_prompt
            
            # 更新所有角色配置中的system_prompt
            if 'characters' in self._config_data:
                for character_name, character_config in self._config_data['characters'].items():
                    if isinstance(character_config, dict):
                        character_config['system_prompt'] = new_prompt
            
            # 保存配置文件
            success = self.save_config()
            if success:
                print(f"✅ 系统提示词已更新并同步到所有配置")
            return success
            
        except Exception as e:
            print(f"❌ 更新系统提示词失败: {e}")
            return False
    
    def update_character_prompt(self, character_name: str, new_prompt: str) -> bool:
        """
        更新指定角色的系统提示词
        
        Args:
            character_name: 角色名称
            new_prompt: 新的系统提示词
            
        Returns:
            bool: 更新是否成功
        """
        try:
            if 'characters' not in self._config_data:
                return False
                
            if character_name not in self._config_data['characters']:
                return False
                
            self._config_data['characters'][character_name]['system_prompt'] = new_prompt
            
            # 保存配置文件
            success = self.save_config()
            if success:
                print(f"✅ 角色 {character_name} 的系统提示词已更新")
            return success
            
        except Exception as e:
            print(f"❌ 更新角色提示词失败: {e}")
            return False


class AppConfigManager:
    """
    应用配置管理器 - 统一的配置应用接口
    """
    
    def __init__(self, config_manager: ConfigManager = None):
        """
        初始化应用配置管理器
        
        Args:
            config_manager: 配置管理器实例，如果不提供则使用全局实例
        """
        self.config_manager = config_manager or get_config_manager()
        self._current_instances = {
            'llm': None,
            'asr': None,
            'tts': None,
            'agent': None
        }
    
    def initialize_default_configs(self) -> bool:
        """
        初始化默认配置选择
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            available = self.config_manager.get_available_configs()
            
            # 设置推荐的默认配置
            recommended_configs = {
                'llm': 'openai_llm',  # 推荐OpenAI作为默认LLM
                'asr': 'openai_whisper',  # 推荐OpenAI Whisper作为默认ASR
                'tts': 'edge_tts',  # 推荐Edge TTS作为默认TTS
                'character': 'default'  # 推荐default作为默认角色
            }
            
            # 应用推荐配置（如果可用）
            for config_type, recommended in recommended_configs.items():
                # 获取正确的配置列表键名
                if config_type == 'character':
                    config_key = 'characters'
                else:
                    config_key = f'{config_type}_configs'
                
                available_list = available.get(config_key, [])
                if recommended in available_list:
                    self.config_manager.set_current_config(config_type, recommended)
                elif available_list:
                    # 如果推荐配置不可用，使用第一个可用配置
                    self.config_manager.set_current_config(config_type, available_list[0])
            
            print("✅ 默认配置初始化完成")
            return True
            
        except Exception as e:
            print(f"❌ 初始化默认配置失败: {e}")
            return False
    
    def get_current_config_for_factory(self, config_type: str) -> Optional[Dict[str, Any]]:
        """
        获取用于工厂创建实例的当前配置
        
        Args:
            config_type: 配置类型 ('llm', 'asr', 'tts', 'character', 'agent')
            
        Returns:
            Dict[str, Any]: 配置数据，如果未设置返回None
        """
        try:
            current_selection = self.config_manager.get_current_selection()
            config_name = current_selection.get(config_type)
            
            if not config_name:
                return None
                
            if config_type == 'llm':
                return self.config_manager.get_llm_config(config_name)
            elif config_type == 'asr':
                return self.config_manager.get_asr_config(config_name)
            elif config_type == 'tts':
                return self.config_manager.get_tts_config(config_name)
            elif config_type == 'character':
                return self.config_manager.get_character_config(config_name)
            elif config_type == 'agent':
                # Agent配置基于当前LLM配置
                llm_name = current_selection.get('llm')
                if llm_name:
                    return self.config_manager.get_agent_config(llm_name)
                return None
            else:
                raise ValueError(f"不支持的配置类型: {config_type}")
        except Exception as e:
            print(f"❌ 获取{config_type}配置失败: {e}")
            return None
    
    def switch_config(self, config_type: str, config_name: str) -> bool:
        """
        切换指定类型的配置
        
        Args:
            config_type: 配置类型 ('llm', 'asr', 'tts', 'character')
            config_name: 配置名称
            
        Returns:
            bool: 切换是否成功
        """
        try:
            success = self.config_manager.set_current_config(config_type, config_name)
            if success:
                # 清除相关的缓存实例，强制重新创建
                self._invalidate_instances(config_type)
                print(f"🔄 {config_type}配置已切换到: {config_name}")
            return success
        except Exception as e:
            print(f"❌ 切换{config_type}配置失败: {e}")
            return False
    
    def _invalidate_instances(self, config_type: str):
        """
        使相关实例缓存失效
        
        Args:
            config_type: 配置类型
        """
        if config_type == 'llm':
            # LLM变更会影响Agent
            self._current_instances['llm'] = None
            self._current_instances['agent'] = None
        elif config_type in self._current_instances:
            self._current_instances[config_type] = None
    
    def get_factory_creation_info(self, config_type: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        获取工厂创建实例所需的信息
        
        Args:
            config_type: 配置类型
            
        Returns:
            Tuple[str, Dict[str, Any]]: (配置名称, 配置参数)，如果未设置返回None
        """
        try:
            current_selection = self.config_manager.get_current_selection()
            config_name = current_selection.get(config_type)
            
            if not config_name:
                return None
            
            config_data = self.get_current_config_for_factory(config_type)
            if not config_data:
                return None
            
            return config_name, config_data
            
        except Exception as e:
            print(f"❌ 获取{config_type}工厂创建信息失败: {e}")
            return None
    
    def get_current_status(self) -> Dict[str, Any]:
        """
        获取当前配置状态
        
        Returns:
            Dict[str, Any]: 当前配置状态
        """
        try:
            selection = self.config_manager.get_current_selection()
            available = self.config_manager.get_available_configs()
            
            status = {
                'current_selection': selection,
                'available_configs': available,
                'config_details': {},
                'factory_ready': {}
            }
            
            # 获取当前配置的详细信息
            for config_type in ['llm', 'asr', 'tts', 'character']:
                if selection.get(config_type):
                    config_data = self.get_current_config_for_factory(config_type)
                    status['config_details'][config_type] = config_data
                    status['factory_ready'][config_type] = config_data is not None
                else:
                    status['factory_ready'][config_type] = False
            
            # Agent配置状态
            agent_config = self.get_current_config_for_factory('agent')
            status['config_details']['agent'] = agent_config
            status['factory_ready']['agent'] = agent_config is not None
            
            return status
            
        except Exception as e:
            print(f"❌ 获取配置状态失败: {e}")
            return {}
    
    def validate_current_configs(self) -> Dict[str, bool]:
        """
        验证当前配置的有效性
        
        Returns:
            Dict[str, bool]: 各配置类型的验证结果
        """
        validation_results = {}
        
        try:
            selection = self.config_manager.get_current_selection()
            
            for config_type in ['llm', 'asr', 'tts', 'character']:
                config_name = selection.get(config_type)
                if config_name:
                    try:
                        config_data = self.get_current_config_for_factory(config_type)
                        validation_results[config_type] = config_data is not None
                    except Exception:
                        validation_results[config_type] = False
                else:
                    validation_results[config_type] = False
            
            # 验证Agent配置
            try:
                agent_config = self.get_current_config_for_factory('agent')
                validation_results['agent'] = agent_config is not None
            except Exception:
                validation_results['agent'] = False
                
        except Exception as e:
            print(f"❌ 验证配置失败: {e}")
        
        return validation_results
    
    def get_config_recommendations(self) -> Dict[str, str]:
        """
        获取配置推荐
        
        Returns:
            Dict[str, str]: 推荐的配置
        """
        try:
            available = self.config_manager.get_available_configs()
            recommendations = {}
            
            # LLM推荐逻辑
            llm_priority = ['openai_llm', 'claude_llm', 'gemini_llm', 'deepseek_llm']
            for llm in llm_priority:
                if llm in available.get('llm_configs', []):
                    recommendations['llm'] = llm
                    break
            
            # ASR推荐逻辑
            asr_priority = ['openai_whisper', 'faster_whisper', 'azure_asr']
            for asr in asr_priority:
                if asr in available.get('asr_configs', []):
                    recommendations['asr'] = asr
                    break
            
            # TTS推荐逻辑
            tts_priority = ['edge_tts', 'azure_tts', 'openai_tts']
            for tts in tts_priority:
                if tts in available.get('tts_configs', []):
                    recommendations['tts'] = tts
                    break
            
            # Character推荐逻辑
            character_priority = ['default', 'assistant', 'friend']
            for character in character_priority:
                if character in available.get('characters', []):
                    recommendations['character'] = character
                    break
            
            return recommendations
            
        except Exception as e:
            print(f"❌ 获取配置推荐失败: {e}")
            return {}
    
    def apply_recommendations(self) -> bool:
        """
        应用推荐的配置
        
        Returns:
            bool: 应用是否成功
        """
        try:
            recommendations = self.get_config_recommendations()
            success = True
            
            for config_type, config_name in recommendations.items():
                if not self.switch_config(config_type, config_name):
                    success = False
            
            if success:
                print("✅ 推荐配置应用成功")
            else:
                print("⚠️  部分推荐配置应用失败")
            
            return success
            
        except Exception as e:
            print(f"❌ 应用推荐配置失败: {e}")
            return False


# 全局配置管理器实例
_config_manager = None
_app_config_manager = None


def get_config_manager() -> ConfigManager:
    """
    获取全局配置管理器实例
    
    Returns:
        ConfigManager: 配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_app_config_manager() -> AppConfigManager:
    """
    获取全局应用配置管理器实例
    
    Returns:
        AppConfigManager: 应用配置管理器实例
    """
    global _app_config_manager
    if _app_config_manager is None:
        _app_config_manager = AppConfigManager()
        # 只有在没有现有配置选择时才初始化默认配置
        current_selection = _app_config_manager.config_manager.get_current_selection()
        if not any(current_selection.values()):
            _app_config_manager.initialize_default_configs()
    return _app_config_manager


# 为了兼容性，保留原有的ConfigCenter接口
class ConfigCenter:
    """配置中心 - 兼容性接口"""
    
    @classmethod
    def get_llm_config(cls, conf_uid: str) -> Dict[str, Any]:
        """获取LLM配置"""
        return get_config_manager().get_llm_config(conf_uid)
    
    @classmethod
    def get_asr_config(cls, conf_uid: str) -> Dict[str, Any]:
        """获取ASR配置"""
        return get_config_manager().get_asr_config(conf_uid)
    
    @classmethod
    def get_tts_config(cls, conf_uid: str) -> Dict[str, Any]:
        """获取TTS配置"""
        return get_config_manager().get_tts_config(conf_uid)
    
    @classmethod
    def get_character_config(cls, character_name: str) -> Dict[str, Any]:
        """获取角色配置"""
        return get_config_manager().get_character_config(character_name)
    
    @classmethod
    def get_agent_config(cls, conf_uid: str, conf_llm_type: str) -> Dict[str, Any]:
        """获取Agent配置"""
        return get_config_manager().get_agent_config(conf_llm_type)
    
    @classmethod
    def get_available_configs(cls) -> Dict[str, list]:
        """获取可用配置列表"""
        return get_config_manager().get_available_configs()
    
    @classmethod
    def reload_config(cls):
        """重新加载配置"""
        get_config_manager().reload_config()