import sys
import asyncio
import logging
import warnings
import live2d.v3 as live2d
from PyQt5.QtWidgets import QApplication
from qasync import QEventLoop
from loguru import logger

from OQWindows.qt_window_main import MainWindow


async def main():
    """主函数 - 启动整合应用"""
    # 设置日志
    logger.remove()
    logger.add(sys.stdout, 
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", 
               level="INFO")

    # 将标准 logging 重定向到 loguru，统一控制台日志格式
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                level = logger.level(record.levelname).name
            except Exception:
                level = record.levelno
            logger.opt(depth=2, exception=record.exc_info).log(level, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    logging.captureWarnings(True)
    # 屏蔽 webrtcvad 的 pkg_resources 过时警告，减少杂讯
    warnings.filterwarnings("ignore", message=r"pkg_resources is deprecated.*")
    
    # 初始化Live2D
    live2d.init()
    
    try:
        # 创建Qt应用
        app = QApplication(sys.argv)

        # 设置qasync事件循环
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # 创建主窗口
        win = MainWindow()
        
        # 初始化后端系统
        logger.info("正在启动OLV-QT语音助手...")
        await win.initialize_backend()
        
        # 显示窗口
        win.show()
        
        # 显示启动完成信息
        logger.success("🎉 OLV-QT语音助手启动成功！")
        logger.info("💡 点击右下角的聊天按钮开始对话")
        logger.info("🎤 支持文字输入和语音输入")
        logger.info("🎭 AI回复会触发Live2D表情动作")
        
        # 运行事件循环
        with loop:
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                logger.info("收到退出信号...")
            finally:
                logger.info("正在清理资源...")
                await win.cleanup()
                
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise
    finally:
        # 清理Live2D
        live2d.dispose()
        logger.info("应用已退出")


if __name__ == "__main__":
    asyncio.run(main())