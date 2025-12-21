"""
File   : app.py
Desc   : Chainlit 应用主入口
Date   : 2025/12/15
Author : Tianyu Chen
"""
import sys
from pathlib import Path
import chainlit as cl
from dotenv import load_dotenv
from loguru import logger

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))
from src.utils.loguru_utils import config_loguru
from src.agent import chat
from src.utils.chainlit_utils import get_model_settings

# 加载环境变量
load_dotenv()

# 应用日志配置
config_loguru()

@logger.catch
@cl.on_chat_start
async def start_chat():
    """
    当用户首次打开聊天时触发。
    目标：初始化聊天会话的内存。
    """
    # 获取并存储模型设置
    model_settings = await get_model_settings()
    cl.user_session.set("model_settings", model_settings)

@logger.catch
@cl.on_settings_update
async def setup_agent(settings):
    """
    当用户更新设置时触发。
    目标：更新聊天模型设置。
    """
    cl.user_session.set("model_settings", settings)
    logger.info(f"\nUpdated model settings: {settings}")

@logger.catch
@cl.on_message
async def main(message: cl.Message):
    """
    当用户发送消息时触发。
    目标：处理用户消息并生成响应。
    """

    await chat(message)
