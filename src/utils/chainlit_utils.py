"""
File   : chainlit_utils.py
Desc   : Chainlit 工具
Date   : 2025/12/21
Author : Tianyu Chen
"""


import chainlit as cl
from chainlit.input_widget import Select, Switch, Slider, TextInput


async def get_model_settings():
    """
    获取聊天模型设置
    """

    settings = await cl.ChatSettings(
        [
            Select(
                id="Model",
                label="聊天模型",
                values=["deepseek-v3.2", "qwen-plus", "qwen3-max"],
                initial_index=0,
            ),
            Switch(
                id="Streaming", 
                label="流式输出", 
                initial=True
            ),
            Switch(
                id="Thinking", 
                label="深度思考", 
                initial=True
            ),
            Slider(
                id="Temperature",
                label="温度",
                initial=1,
                min=0,
                max=2,
                step=0.1,
            ),
            Slider(
                id="MaxTokens",
                label="最大令牌数",
                initial=2048,
                min=1024,
                max=10240,
                step=1,
            ),
            TextInput(
                id="RoleSetting",
                label="角色设定", 
                initial="你是一个超级人工智能助手，名字叫泰迪 🧸，你乐于帮助用户完成各种任务。"
            ),
        ]
    ).send()
    return settings
