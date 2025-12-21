"""
File   : loguru_utils.py
Desc   : loguru 日志工具
Date   : 2025/08/21
Author : Tianyu Chen
"""
import sys
from pathlib import Path
from loguru import logger

# 日志文件名
LOG_FILE_NAME = 'logs/app.log'
# 日志轮转策略
# 文件大小：支持 "B", "KB", "MB", "GB" 等单位
# 时间周期：如 "00:00" 每天午夜轮转，"W0" 每周一午夜轮转
LOG_ROTATION = "W0"
# 日志保留策略
# # 支持整数（文件数量）或字符串（时间，如"7 days", " "1 weeks", "2 months" 等)
LOG_RETENTION = "6 months"


def config_loguru(log_file_name: str = LOG_FILE_NAME):
    """
    初始化日志配置
    """
    # 1. 移除默认的控制台输出
    logger.remove()

    # 2. 确保日志目录存在
    Path('logs').mkdir(parents=True, exist_ok=True)

    # 3. 添加输出到控制台的 Sink
    console_formatter = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<yellow>p:{process.id}</yellow> | "
        "<magenta>t:{thread.name}</magenta> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level> "
    )
    logger.add(
        sys.stdout,  # 输出到标准输出
        level="DEBUG",  # 控制台日志级别
        format=console_formatter,
        enqueue=True,  # 设置为 True 使日志记录异步，提高性能
        backtrace=True,  # 记录完整的堆栈跟踪
        diagnose=True    # 添加异常链等诊断信息
    )

    # 4. 添加输出到文件的 Sink
    file_formatter = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "p:{process.id} | " # 进程ID
        "t:{thread.name} ({thread.id}) | " # 线程名和线程ID
        "{name}:{function}:{line} - {message}"
    )
    logger.add(
        log_file_name,
        level="DEBUG",  # 文件日志级别
        format=file_formatter,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,  # 设置保留策略
        encoding='utf-8',
        enqueue=True,  # 设置为 True 使日志记录异步，提高性能
        backtrace=True,  # 记录完整的堆栈跟踪
        diagnose=True    # 添加异常链等诊断信息
    )


if __name__ == "__main__":
    # 测试日志记录
    import time
    config_loguru()

    @logger.catch
    def my_function(x, y):
        return x / y

    for i in range(10):
        logger.debug("这是一个调试信息")
        logger.info(f"这是一个普通信息, index={i}")
        time.sleep(1)

    my_function(10, 0) # 测试异常捕获
