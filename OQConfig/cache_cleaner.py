"""
缓存清理工具模块
用于在应用关闭时自动清理TTS音频缓存文件
"""

import os
import glob
from pathlib import Path
from loguru import logger


class CacheCleaner:
    """缓存清理器"""
    
    def __init__(self, cache_dir: str = None):
        """
        初始化缓存清理器
        
        Args:
            cache_dir: 缓存目录路径，如果为None则使用默认路径
        """
        if cache_dir is None:
            # 获取项目根目录下的cache文件夹
            project_root = Path(__file__).parent.parent
            self.cache_dir = project_root / "cache"
        else:
            self.cache_dir = Path(cache_dir)
    
    def clean_tts_cache(self) -> tuple[int, int]:
        """
        清理TTS音频缓存文件
        
        Returns:
            tuple: (成功删除的文件数, 删除失败的文件数)
        """
        if not self.cache_dir.exists():
            logger.info(f"缓存目录不存在: {self.cache_dir}")
            return 0, 0
        
        # 定义TTS音频文件的匹配模式
        tts_patterns = [
            "stream_tts_seq_*.mp3",
            "stream_tts_final_seq_*.mp3"
        ]
        
        success_count = 0
        failed_count = 0
        
        logger.info(f"开始清理TTS缓存文件，目录: {self.cache_dir}")
        
        for pattern in tts_patterns:
            # 使用glob查找匹配的文件
            pattern_path = self.cache_dir / pattern
            matching_files = glob.glob(str(pattern_path))
            
            for file_path in matching_files:
                try:
                    os.remove(file_path)
                    success_count += 1
                    logger.debug(f"已删除缓存文件: {Path(file_path).name}")
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"删除缓存文件失败 {Path(file_path).name}: {e}")
        
        if success_count > 0 or failed_count > 0:
            logger.info(f"TTS缓存清理完成: 成功删除 {success_count} 个文件, 失败 {failed_count} 个文件")
        else:
            logger.info("没有找到需要清理的TTS缓存文件")
        
        return success_count, failed_count
    
    def clean_all_cache(self) -> tuple[int, int]:
        """
        清理所有缓存文件（包括TTS和其他可能的缓存）
        
        Returns:
            tuple: (成功删除的文件数, 删除失败的文件数)
        """
        if not self.cache_dir.exists():
            logger.info(f"缓存目录不存在: {self.cache_dir}")
            return 0, 0
        
        success_count = 0
        failed_count = 0
        
        logger.info(f"开始清理所有缓存文件，目录: {self.cache_dir}")
        
        # 遍历缓存目录中的所有文件
        for file_path in self.cache_dir.iterdir():
            if file_path.is_file():
                try:
                    file_path.unlink()
                    success_count += 1
                    logger.debug(f"已删除缓存文件: {file_path.name}")
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"删除缓存文件失败 {file_path.name}: {e}")
        
        if success_count > 0 or failed_count > 0:
            logger.info(f"缓存清理完成: 成功删除 {success_count} 个文件, 失败 {failed_count} 个文件")
        else:
            logger.info("缓存目录为空，无需清理")
        
        return success_count, failed_count
    
    def get_cache_info(self) -> dict:
        """
        获取缓存目录信息
        
        Returns:
            dict: 包含缓存文件统计信息的字典
        """
        if not self.cache_dir.exists():
            return {
                "cache_dir": str(self.cache_dir),
                "exists": False,
                "total_files": 0,
                "tts_files": 0,
                "total_size_mb": 0
            }
        
        total_files = 0
        tts_files = 0
        total_size = 0
        
        for file_path in self.cache_dir.iterdir():
            if file_path.is_file():
                total_files += 1
                total_size += file_path.stat().st_size
                
                # 检查是否为TTS文件
                if (file_path.name.startswith("stream_tts_seq_") or 
                    file_path.name.startswith("stream_tts_final_seq_")) and file_path.suffix == ".mp3":
                    tts_files += 1
        
        return {
            "cache_dir": str(self.cache_dir),
            "exists": True,
            "total_files": total_files,
            "tts_files": tts_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }


def get_cache_cleaner() -> CacheCleaner:
    """
    获取缓存清理器实例
    
    Returns:
        CacheCleaner: 缓存清理器实例
    """
    return CacheCleaner()


# 便捷函数
def clean_tts_cache() -> tuple[int, int]:
    """
    清理TTS缓存文件的便捷函数
    
    Returns:
        tuple: (成功删除的文件数, 删除失败的文件数)
    """
    cleaner = get_cache_cleaner()
    return cleaner.clean_tts_cache()


def clean_all_cache() -> tuple[int, int]:
    """
    清理所有缓存文件的便捷函数
    
    Returns:
        tuple: (成功删除的文件数, 删除失败的文件数)
    """
    cleaner = get_cache_cleaner()
    return cleaner.clean_all_cache()