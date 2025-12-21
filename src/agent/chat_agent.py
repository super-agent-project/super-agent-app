"""
File   : chat_agent.py
Desc   : 聊天智能体
Date   : 2025/12/21
Author : Tianyu Chen
"""

import os
import time
import chainlit as cl
from openai import AsyncOpenAI
from loguru import logger

# 引入优化后的 UI 工具
from src.ui import get_thinking_html, get_finished_thinking_html


# 初始化 Client
client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"), base_url=os.environ.get("OPENAI_BASE_URL"))


async def chat(message: cl.Message):
    """
    主聊天入口函数
    """
    logger.info("\n\n\n==================[System] New message received. Processing...==================")

    # 0. 获取历史记录与设置
    message_history = cl.user_session.get("message_history", [])
    model_settings = cl.user_session.get("model_settings")
    user_query = message.content
    
    logger.info(f"\n[User] {message.content}")

    # 1. UI 消息容器
    final_answer = cl.Message(content="")
    await final_answer.send()
    
    # 2. 根据设置选择处理模式
    answer_content = ""
    start_time = time.time()

    try:
        if model_settings["Streaming"]:
            logger.info("\n[System] Mode: Streaming")
            answer_content = await process_streaming_response(
                client, model_settings, message_history, user_query, final_answer, start_time
            )
        else:
            logger.info("\n[System] Mode: Blocking (Non-Streaming)")
            answer_content = await process_blocking_response(
                client, model_settings, message_history, user_query, final_answer, start_time
            )
    except Exception as e:
        error_msg = f"Error during generation: {str(e)}"
        logger.error(f"[System] {error_msg}")
        final_answer.content += f"\n\n⚠️ {error_msg}"
        await final_answer.update()
        return

    # 3. 将纯回答文本存入历史记忆
    message_history.append({"role": "assistant", "content": answer_content})
    cl.user_session.set("message_history", message_history)

    logger.info("\n==================[System] Message processing completed.]==================\n\n")


async def call_model(client, model_settings, message_history, user_query):
    """
    调用聊天模型接口
    """

    PROMPT = f"""
    # 角色设定
    {model_settings['RoleSetting']}

    # 用户问题
    {user_query}
    """

    # 添加用户消息到历史记录
    message_history.append({"role": "user", "content": PROMPT})

    response = await client.chat.completions.create(
        model=model_settings["Model"],
        messages=message_history,
        temperature=model_settings["Temperature"],
        max_tokens=int(model_settings["MaxTokens"]),
        stream=model_settings["Streaming"],
        extra_body={"enable_thinking": model_settings["Thinking"]}
    )
    return response

async def process_streaming_response(client, model_settings, message_history, user_query, final_answer, start_time):
    """
    处理流式输出 (Streaming = True)
    """
    thinking_buffer = ""
    answer_content = ""
    is_thinking_phase = model_settings["Thinking"]

    stream = await call_model(client, model_settings, message_history, user_query)

     # === A. 处理流式响应 ===
    async for chunk in stream:
        delta = chunk.choices[0].delta
        
        # 兼容不同厂商的 reasoning 字段 (DeepSeek 通常用 reasoning_content)
        reasoning = getattr(delta, "reasoning_content", None)
        content = delta.content

        # === A. 处理思考 (Reasoning) ===
        if reasoning and is_thinking_phase:
            thinking_buffer += reasoning
            final_answer.content = get_thinking_html(thinking_buffer)
            await final_answer.update()
            # print(reasoning, end="", flush=True) # 可选：减少控制台噪音
        
        # === B. 处理正文 (Content) ===
        elif content:
            if is_thinking_phase:
                duration = int(time.time() - start_time)
                if duration < 1: duration = 1
                
                # 结束思考阶段，锁定 HTML
                final_thinking_html = get_finished_thinking_html(thinking_buffer, duration)
                final_answer.content = final_thinking_html

                # 添加两个换行符，强制将后续内容与 HTML 分离
                final_answer.content += "\n\n"
                
                is_thinking_phase = False 

                logger.debug(f"\n[🧠 Thinking] {thinking_buffer}")
                logger.info(f"\n[System] Thinking finished. Duration: {duration}s")
            
            answer_content += content
            
            # 必须重新拼接：已完成的思考HTML + 当前生成的正文
            # 注意：final_answer.content 在上面被重置为 final_thinking_html 了，所以这里直接 += 即可
            # 但为了防止逻辑混乱，建议总是全量赋值或确保 content 是追加模式
            # 这里由于 is_thinking_phase 切换时已经重置了 content，所以可以直接追加
            final_answer.content += content 
            await final_answer.update()
            # print(content, end="", flush=True)

    # === C. 兜底处理 (如果只有思考没有内容，或者流结束时还在思考) ===
    if is_thinking_phase and thinking_buffer:
        duration = int(time.time() - start_time)
        final_answer.content = get_finished_thinking_html(thinking_buffer, duration)
        await final_answer.update()

    logger.debug(f"\n[🧸 Answer] {answer_content}")
    logger.info("\n[System] Stream finished.")
    return answer_content


async def process_blocking_response(client, model_settings, message_history, user_query, final_answer, start_time):
    """
    处理非流式输出 (Streaming = False)
    """
    # 提示用户正在等待响应
    final_answer.content = "生成中..."
    await final_answer.update()

    response = await call_model(client, model_settings, message_history, user_query)
    message = response.choices[0].message
    
    # 获取内容和思考过程
    answer_content = message.content if message.content else ""
    # 非流式模式下，reasoning_content 通常也在 message 对象中
    reasoning_content = getattr(message, "reasoning_content", "")
    
    duration = int(time.time() - start_time)
    if duration < 1: duration = 1

    # 构建最终 UI 内容
    final_ui_content = ""

    # 如果有思考过程，先添加思考块
    if reasoning_content:
        final_ui_content += get_finished_thinking_html(reasoning_content, duration)
        # HTML 块之后添加换行
        final_ui_content += "\n\n"
        logger.debug(f"\n[🧠 Thinking] {reasoning_content}")

    # 添加正文
    final_ui_content += answer_content

    # 一次性更新 UI
    final_answer.content = final_ui_content
    await final_answer.update()

    logger.debug(f"\n[🧸 Answer] {answer_content}")
    logger.info(f"\n[System] Request finished. Duration: {duration}s")
    return answer_content
