"""
Live2D表情控制器
提供各种表情控制功能，包括嘴巴动作控制
"""

import time
import threading
from typing import Optional, Callable
from loguru import logger


class ExpressionController:
    """Live2D表情控制器"""
    
    def __init__(self, model=None):
        """
        初始化表情控制器
        
        Args:
            model: Live2D模型实例
        """
        self.model = model
        self.mouth_thread: Optional[threading.Thread] = None
        self.mouth_running = False
        self.mouth_cycle_time = 0.3  # 默认1秒循环
        
    def set_model(self, model):
        """设置Live2D模型"""
        self.model = model
        
    def set_parameter_value(self, param_name: str, value: float, weight: float = 1.0):
        """设置模型参数值
        
        Args:
            param_name (str): 参数名称
            value (float): 参数值
            weight (float): 权重
        """
        if self.model and hasattr(self.model, 'SetParameterValue'):
            try:
                self.model.SetParameterValue(param_name, value, weight)
                logger.debug(f"[Expression] 设置参数 {param_name} = {value}")
            except Exception as e:
                logger.error(f"[Expression] 设置参数失败: {e}")
        else:
            logger.warning("[Expression] 模型未设置或不支持SetParameterValue方法")
            
    def set_mouth_open(self, value: float):
        """设置嘴巴张开程度
        
        Args:
            value (float): 张开程度，0.0为完全关闭，1.0为完全张开
        """
        self.set_parameter_value("ParamMouthOpenY", value)
        
    def set_mouth_form(self, value: float):
        """设置嘴巴形状
        
        Args:
            value (float): 嘴巴形状值，通常-1.0到1.0
        """
        self.set_parameter_value("ParamMouthForm", value)
        
    def start_mouth_cycle(self, cycle_time: float = 1.0, callback: Optional[Callable] = None):
        """开始嘴巴循环动作（一秒张开一秒关闭）
        
        Args:
            cycle_time (float): 循环时间，单位秒
            callback (Callable): 状态变化回调函数
        """
        if self.mouth_running:
            logger.warning("[Expression] 嘴巴循环已在运行")
            return
            
        self.mouth_cycle_time = cycle_time
        self.mouth_running = True
        
        def mouth_cycle_worker():
            """嘴巴循环工作线程"""
            mouth_open = False
            logger.info(f"[Expression] 开始嘴巴循环，周期: {cycle_time}秒")
            
            while self.mouth_running:
                try:
                    # 切换嘴巴状态
                    mouth_open = not mouth_open
                    mouth_value = 1.0 if mouth_open else 0.0
                    self.set_mouth_open(mouth_value)
                    
                    # 调用回调函数
                    if callback:
                        callback(mouth_open, mouth_value)
                    
                    state_text = "张开" if mouth_open else "关闭"
                    logger.debug(f"[Expression] 嘴巴状态: {state_text}")
                    
                    # 等待指定时间
                    time.sleep(cycle_time)
                    
                except Exception as e:
                    logger.error(f"[Expression] 嘴巴循环错误: {e}")
                    break
                    
            # 循环结束，重置嘴巴状态
            self.set_mouth_open(0.0)
            logger.info("[Expression] 嘴巴循环结束")
            
        # 启动工作线程
        self.mouth_thread = threading.Thread(target=mouth_cycle_worker, daemon=True)
        self.mouth_thread.start()
        
    def stop_mouth_cycle(self):
        """停止嘴巴循环动作"""
        if self.mouth_running:
            self.mouth_running = False
            logger.info("[Expression] 停止嘴巴循环")
            
            # 等待线程结束
            if self.mouth_thread and self.mouth_thread.is_alive():
                self.mouth_thread.join(timeout=2.0)
                
            # 重置嘴巴状态
            self.set_mouth_open(0.0)
        else:
            logger.warning("[Expression] 嘴巴循环未在运行")
            
    def is_mouth_cycle_running(self) -> bool:
        """检查嘴巴循环是否正在运行"""
        return self.mouth_running
        
    def set_expression(self, expression_name: str):
        """设置表情
        
        Args:
            expression_name (str): 表情名称
        """
        if self.model and hasattr(self.model, 'SetExpression'):
            try:
                self.model.SetExpression(expression_name)
                logger.info(f"[Expression] 设置表情: {expression_name}")
            except Exception as e:
                logger.error(f"[Expression] 设置表情失败: {e}")
        else:
            logger.warning("[Expression] 模型未设置或不支持SetExpression方法")
            
    def set_random_expression(self):
        """设置随机表情"""
        if self.model and hasattr(self.model, 'SetRandomExpression'):
            try:
                self.model.SetRandomExpression()
                logger.info("[Expression] 设置随机表情")
            except Exception as e:
                logger.error(f"[Expression] 设置随机表情失败: {e}")
        else:
            logger.warning("[Expression] 模型未设置或不支持SetRandomExpression方法")
            
    def cleanup(self):
        """清理资源"""
        self.stop_mouth_cycle()
        logger.info("[Expression] 表情控制器清理完成")


# 全局表情控制器实例
_global_expression_controller: Optional[ExpressionController] = None


def get_expression_controller() -> ExpressionController:
    """获取全局表情控制器实例"""
    global _global_expression_controller
    if _global_expression_controller is None:
        _global_expression_controller = ExpressionController()
    return _global_expression_controller


def init_expression_controller(model) -> ExpressionController:
    """初始化全局表情控制器
    
    Args:
        model: Live2D模型实例
        
    Returns:
        ExpressionController: 表情控制器实例
    """
    controller = get_expression_controller()
    controller.set_model(model)
    logger.info("[Expression] 全局表情控制器初始化完成")
    return controller


# 便捷函数
def start_mouth_animation(cycle_time: float = 1.0):
    """开始嘴巴动画（便捷函数）"""
    controller = get_expression_controller()
    controller.start_mouth_cycle(cycle_time)


def stop_mouth_animation():
    """停止嘴巴动画（便捷函数）"""
    controller = get_expression_controller()
    controller.stop_mouth_cycle()


def set_mouth_open_value(value: float):
    """设置嘴巴张开程度（便捷函数）"""
    controller = get_expression_controller()
    controller.set_mouth_open(value)