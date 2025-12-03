"""
日志管理模块

基于 loguru 的日志管理，提供初始化配置功能
所有代码可以直接使用: from loguru import logger
"""

import logging
import sys
from typing import Optional, Union

from loguru import logger as loguru_logger
from dynaconf import Dynaconf

from .config import get_settings

logger = loguru_logger


def setup_logging(config: Optional[Union[str, Dynaconf]] = None) -> None:
    """
    根据配置文件或配置对象初始化 loguru 日志系统
    
    Args:
        config: 配置文件路径或配置对象（Dynaconf），如果为 None 则使用默认配置
    """
    if isinstance(config, Dynaconf):
        # 如果传入的是配置对象，直接使用
        config_obj = config
    else:
        # 如果传入的是配置文件路径或 None，则获取配置对象
        config_obj = get_settings(config)
    
    # 移除默认的 handler
    loguru_logger.remove()
    
    # 获取日志级别和格式
    log_level = config_obj.get("logging.level", "INFO").upper()
    
    # 检查是否使用 JSON 格式
    use_json = config_obj.get("logging.json", False)
    if isinstance(use_json, str):
        use_json = use_json.lower() in ("true", "1", "yes", "on")
    
    # 如果启用 JSON 格式，使用 serialize
    if use_json:
        # JSON 格式不需要 format 参数，使用 serialize=True
        console_kwargs = {
            "sink": sys.stdout,
            "serialize": True,
            "level": log_level,
            "backtrace": True,
            "diagnose": True,
        }
        file_kwargs = {
            "serialize": True,
            "level": log_level,
            "rotation": "10 MB",
            "retention": "7 days",
            "compression": "zip",
            "backtrace": True,
            "diagnose": True,
        }
    else:
        # 获取日志格式，如果是标准 logging 格式则转换为 loguru 格式
        user_format = config_obj.get("logging.format", None)
        if user_format:
            # 如果用户使用的是标准 logging 格式，尝试转换
            # 简单的格式转换（常见格式）
            if "%(asctime)s" in user_format:
                user_format = user_format.replace("%(asctime)s", "{time:YYYY-MM-DD HH:mm:ss}")
            if "%(name)s" in user_format:
                user_format = user_format.replace("%(name)s", "{name}")
            if "%(levelname)s" in user_format:
                user_format = user_format.replace("%(levelname)s", "{level: <8}")
            if "%(message)s" in user_format:
                user_format = user_format.replace("%(message)s", "{message}")
            if "%(filename)s" in user_format:
                user_format = user_format.replace("%(filename)s", "{file.name}")
            if "%(funcName)s" in user_format:
                user_format = user_format.replace("%(funcName)s", "{function}")
            if "%(lineno)d" in user_format:
                user_format = user_format.replace("%(lineno)d", "{line}")
            log_format = user_format
        else:
            # 默认 loguru 格式
            log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        
        console_kwargs = {
            "sink": sys.stdout,
            "format": log_format,
            "level": log_level,
            "colorize": True,
            "backtrace": True,
            "diagnose": True,
        }
        file_kwargs = {
            "format": log_format,
            "level": log_level,
            "rotation": "10 MB",
            "retention": "7 days",
            "compression": "zip",
            "backtrace": True,
            "diagnose": True,
        }
    
    # 添加控制台输出 handler
    loguru_logger.add(**console_kwargs)
    
    # 如果有文件日志配置，添加文件 handler
    log_file = config_obj.get("logging.file")
    if log_file:
        import os
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else ".", exist_ok=True)
        loguru_logger.add(log_file, **file_kwargs)
    
    # 配置第三方库的日志级别（仅设置标准 logging 的级别，不拦截转发）
    try:
        third_party_config = config_obj.logging.third_party
    except (AttributeError, KeyError):
        try:
            third_party_config = config_obj.get("logging.third_party", {})
        except (AttributeError, KeyError):
            third_party_config = {}
    
    # 为每个配置的第三方库设置日志级别
    if isinstance(third_party_config, dict):
        for logger_name, level_name in third_party_config.items():
            if isinstance(level_name, str):
                std_logger = logging.getLogger(logger_name)
                # 设置标准 logging 的级别
                level = getattr(logging, level_name.upper(), logging.INFO)
                std_logger.setLevel(level)


# 为了向后兼容，提供 get_logger 函数
# 但实际上直接使用 loguru 的 logger 即可
def get_logger(name: str = "app"):
    """
    获取日志器实例（向后兼容）
    
    注意：建议直接使用 `from loguru import logger`
    
    Args:
        name: 日志器名称（loguru 中用于标识，可通过 bind 方法绑定）
        
    Returns:
        loguru Logger 实例
    """
    return loguru_logger.bind(name=name)


# 为了向后兼容，提供 Logger 类
class Logger:
    """
    日志器类（向后兼容）
    
    注意：建议直接使用 `from loguru import logger`
    """
    
    def __init__(self, name: str = "app"):
        """
        初始化日志器
        
        Args:
            name: 日志器名称
        """
        self.name = name
        self._logger = loguru_logger.bind(name=name)
    
    def debug(self, message: str, *args, **kwargs) -> None:
        """记录调试日志"""
        self._logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs) -> None:
        """记录信息日志"""
        self._logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs) -> None:
        """记录警告日志"""
        self._logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs) -> None:
        """记录错误日志"""
        self._logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs) -> None:
        """记录严重错误日志"""
        self._logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs) -> None:
        """记录异常日志"""
        self._logger.exception(message, *args, **kwargs)
