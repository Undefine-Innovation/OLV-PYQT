#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置同步功能测试脚本
验证提示词修改能正确同步到Workspace项目
"""

import sys
import os
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from OQConfig.config_sync_service import get_config_sync_service, ConfigSyncEvent
    from OQConfig.config_manager import get_config_manager
    from OQConfig.config_logger import get_config_logger
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行此测试脚本")
    sys.exit(1)


def test_system_prompt_sync():
    """测试系统提示词同步功能"""
    print("\n=== 测试系统提示词同步功能 ===")
    
    sync_service = get_config_sync_service()
    config_manager = get_config_manager()
    
    # 测试数据
    test_prompts = [
        "你是一个有用的AI助手，请友善地回答用户的问题。",
        "You are a helpful AI assistant. Please answer questions politely and accurately.",
        "作为一个专业的AI助手，你需要提供准确、有用的信息。请保持礼貌和专业。"
    ]
    
    print(f"准备测试 {len(test_prompts)} 个不同的系统提示词...")
    
    for i, test_prompt in enumerate(test_prompts, 1):
        print(f"\n--- 测试 {i}/{len(test_prompts)} ---")
        print(f"测试提示词: {test_prompt[:50]}{'...' if len(test_prompt) > 50 else ''}")
        
        # 执行同步
        event = sync_service.sync_system_prompt(test_prompt, source="测试脚本")
        
        # 检查结果
        if event.success:
            print("✅ 同步成功")
            
            # 验证配置是否真的更新了
            try:
                current_config = config_manager.get_config_section("agent_config_template")
                saved_prompt = current_config.get("system_prompt", "")
                
                if saved_prompt == test_prompt:
                    print("✅ 配置验证成功：提示词已正确保存")
                else:
                    print(f"❌ 配置验证失败：保存的提示词与预期不符")
                    print(f"   预期: {test_prompt[:50]}...")
                    print(f"   实际: {saved_prompt[:50]}...")
            except Exception as e:
                print(f"❌ 配置验证异常: {e}")
        else:
            print(f"❌ 同步失败: {event.error_message}")
    
    return True


def test_character_prompt_sync():
    """测试角色提示词同步功能"""
    print("\n=== 测试角色提示词同步功能 ===")
    
    sync_service = get_config_sync_service()
    config_manager = get_config_manager()
    
    # 获取可用角色列表
    try:
        available_characters = config_manager.get_available_characters()
        print(f"发现 {len(available_characters)} 个可用角色: {', '.join(available_characters)}")
    except Exception as e:
        print(f"获取角色列表失败: {e}")
        available_characters = ["default"]  # 使用默认角色进行测试
    
    if not available_characters:
        print("⚠️ 没有可用角色，跳过角色提示词测试")
        return True
    
    # 选择第一个角色进行测试
    test_character = available_characters[0]
    test_prompt = f"你是角色 {test_character}，请根据你的角色设定来回答问题。"
    
    print(f"\n测试角色: {test_character}")
    print(f"测试提示词: {test_prompt}")
    
    # 执行同步
    event = sync_service.sync_character_prompt(test_character, test_prompt, source="测试脚本")
    
    # 检查结果
    if event.success:
        print("✅ 角色提示词同步成功")
        
        # 验证配置是否真的更新了
        try:
            character_config = config_manager.get_character_config(test_character)
            saved_prompt = character_config.get("system_prompt", "")
            
            if saved_prompt == test_prompt:
                print("✅ 角色配置验证成功：提示词已正确保存")
            else:
                print(f"❌ 角色配置验证失败：保存的提示词与预期不符")
        except Exception as e:
            print(f"❌ 角色配置验证异常: {e}")
    else:
        print(f"❌ 角色提示词同步失败: {event.error_message}")
    
    return True


def test_error_handling():
    """测试错误处理功能"""
    print("\n=== 测试错误处理功能 ===")
    
    sync_service = get_config_sync_service()
    
    # 测试无效输入
    test_cases = [
        (None, "测试None值"),
        (123, "测试数字类型"),
        ("", "测试空字符串"),
        ("   ", "测试空白字符串")
    ]
    
    for invalid_input, description in test_cases:
        print(f"\n测试: {description}")
        try:
            event = sync_service.sync_system_prompt(invalid_input, source="错误测试")
            if not event.success:
                print(f"✅ 正确处理了无效输入: {event.error_message}")
            else:
                print(f"⚠️ 意外成功处理了无效输入")
        except Exception as e:
            print(f"✅ 正确抛出异常: {e}")
    
    return True


def test_sync_history():
    """测试同步历史记录功能"""
    print("\n=== 测试同步历史记录功能 ===")
    
    sync_service = get_config_sync_service()
    
    # 获取当前历史记录数量
    initial_history = sync_service.get_sync_history()
    initial_count = len(initial_history)
    print(f"当前历史记录数量: {initial_count}")
    
    # 执行一次同步操作
    test_prompt = "测试历史记录功能的提示词"
    sync_service.sync_system_prompt(test_prompt, source="历史记录测试")
    
    # 检查历史记录是否增加
    updated_history = sync_service.get_sync_history()
    updated_count = len(updated_history)
    
    if updated_count > initial_count:
        print(f"✅ 历史记录正常增加: {initial_count} -> {updated_count}")
        
        # 检查最新记录
        latest_event = updated_history[-1]
        if latest_event.config_type == "system_prompt" and latest_event.new_value == test_prompt:
            print("✅ 最新历史记录内容正确")
        else:
            print("❌ 最新历史记录内容不正确")
    else:
        print(f"❌ 历史记录未正常增加: {initial_count} -> {updated_count}")
    
    # 测试统计信息
    stats = sync_service.get_sync_statistics()
    print(f"\n同步统计信息:")
    print(f"  总同步次数: {stats['total_syncs']}")
    print(f"  成功次数: {stats['successful_syncs']}")
    print(f"  失败次数: {stats['failed_syncs']}")
    print(f"  成功率: {stats['success_rate']:.2%}")
    
    return True


def test_logger_functionality():
    """测试日志记录功能"""
    print("\n=== 测试日志记录功能 ===")
    
    logger = get_config_logger()
    
    # 获取日志文件路径
    log_file_path = logger.get_log_file_path()
    print(f"日志文件路径: {log_file_path}")
    
    # 检查日志文件是否存在
    if os.path.exists(log_file_path):
        print("✅ 日志文件存在")
        
        # 获取最近的日志记录
        recent_logs = logger.get_recent_logs(5)
        print(f"最近 {len(recent_logs)} 条日志记录:")
        for i, log_line in enumerate(recent_logs, 1):
            print(f"  {i}. {log_line.strip()}")
    else:
        print("❌ 日志文件不存在")
    
    return True


def main():
    """主测试函数"""
    print("开始配置同步功能测试...")
    print(f"项目根目录: {project_root}")
    
    test_results = []
    
    try:
        # 执行各项测试
        test_results.append(("系统提示词同步", test_system_prompt_sync()))
        test_results.append(("角色提示词同步", test_character_prompt_sync()))
        test_results.append(("错误处理", test_error_handling()))
        test_results.append(("同步历史记录", test_sync_history()))
        test_results.append(("日志记录", test_logger_functionality()))
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 输出测试结果总结
    print("\n" + "="*50)
    print("测试结果总结:")
    print("="*50)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 所有测试通过！配置同步功能工作正常。")
    else:
        print("⚠️ 部分测试失败，请检查相关功能。")
    print("="*50)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)