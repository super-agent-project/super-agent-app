"""
File   : chat_agent.py
Desc   : MCP ReAct 智能体
Date   : 2025/12/23
Author : Tianyu Chen
"""

import sys
import json
import time
import shlex
from pathlib import Path
import chainlit as cl
from openai import AsyncOpenAI
from loguru import logger

# 引入基础设施层
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.mcp_client import mcp_client_instance

# 初始化 Client
client = AsyncOpenAI()

async def react(message: cl.Message):
    """
    ReAct 智能体入口
    """
    logger.info("\n\n\n==================[System] New message received. Processing...==================")
    logger.info(f"\n[User] {message.content}")
    user_input = message.content.strip()

    # === 帮助命令处理 ===
    help_content="""
**Available Commands!**

- Use `@folders` to see available topics
- Use `@<topic>` to search papers in that topic
- Use `/prompts` to list available prompts
- Use `/prompt <name> <arg1=value1>` to execute a prompt"
"""
    if user_input.startswith("@help"):
        await cl.Message(content=help_content).send()
        return
    
    # === A. 资源查看 (@resource) ===
    if user_input.startswith("@"):
        uri_suffix = user_input[1:].strip()
        uri = "papers://folders" if uri_suffix == "folders" else f"papers://{uri_suffix}"
        
        async with cl.Step(name="Fetch Resource") as step:
            step.input = uri
            try:
                content = await mcp_client_instance.read_resource(uri)
                step.output = content[:500] + "..." if len(content) > 500 else content
            except Exception as e:
                step.output = f"Error: {str(e)}"
        
        await cl.Message(content=f"📄 **Resource Content**:\n\n{content}\n").send()
        return

    # === B. 列出 Prompts (/prompts) ===
    if user_input == "/prompts":
        prompts = mcp_client_instance.get_available_prompts()
        out_lines = ["📋 **Available Prompts**:"]
        for prompt in prompts:
            out_lines.append(f"- **{prompt['name']}**: {prompt['description']}")
            if prompt['arguments']:
                out_lines.append("  - Arguments:")
                for arg in prompt['arguments']:
                    arg_name = arg.name if hasattr(arg, 'name') else arg.get('name', '')
                    out_lines.append(f"    - {arg_name}")
        await cl.Message(content="\n".join(out_lines)).send()
        return

    # === C. 执行 Prompt (/prompt) ===
    if user_input.startswith("/prompt"):
        # try-except 用于捕获引号不匹配的情况（比如只写了一个 "）
        try:
            # 使用 shlex.split 来解析参数
            parts = shlex.split(user_input)
        except ValueError as e:
            await cl.Message(content=f"⚠️ 参数解析错误: 引号未闭合 ({e})").send()
            return

        if len(parts) < 2:
            await cl.Message(content="用法: `/prompt <name> <arg1=value1> ...`").send()
            return

        prompt_name = parts[1]
        args = {}

        # <--- 3. 遍历解析后的部分
        for arg in parts[2:]:
            if '=' in arg:
                k, v = arg.split('=', 1)
                args[k] = v
            else:
                # 可选：处理没有等号的情况，或者直接忽略
                pass

        async with cl.Step(name="Execute Prompt") as step:
            step.input = f"Prompt: {prompt_name}, Args: {args}"
            try:
                prompt_content = await mcp_client_instance.get_prompt(prompt_name, args)
                # 兼容处理：有的 Prompt 返回对象，有的返回 list
                final_input = str(prompt_content.messages[0].content.text) if hasattr(prompt_content, 'messages') else str(prompt_content)
                step.output = final_input
            except Exception as e:
                step.output = f"Error: {e}"
                await cl.Message(content=f"❌ Prompt Error: {e}").send()
                return

        user_input = final_input

    # 2. 进入 ReAct 循环逻辑
    await run_react_cycle(user_input)
    logger.info("\n==================[System] Message processing completed.]==================\n\n")

def get_system_prompt(model_settings):
    """
    获取系统提示词
    """
    return f"""  
# Role
{model_settings['RoleSetting']}

# Background
- Current System Time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}

# Workflow
- You will alternate between thinking, acting (using tools available), observing (tool results), and answering.
- If no tools are needed, provide a direct answer in clear and concise Markdown format.

# Constraints
- Do speak in Chinese.
- **Use standard Markdown formatting.**
- When using tools, ensure your tool calls are well-formed.
    """

async def run_react_cycle(user_query: str):
    """
    ReAct 核心循环 (Text -> Tool -> Text)
    """
    # 获取上下文
    message_history = cl.user_session.get("message_history", [])
    model_settings = cl.user_session.get("model_settings")
    
    # 构造 System Prompt
    system_prompt = get_system_prompt(model_settings)
    if not message_history or message_history[0]["role"] != "system":
        message_history.insert(0, {"role": "system", "content": system_prompt})
    else:
        message_history[0]["content"] = system_prompt
    
    message_history.append({"role": "user", "content": user_query})
    
    # 懒加载消息对象（不立即发送）
    current_message = cl.Message(content="")

    MAX_ROUNDS = 10
    current_round = 0
    
    while current_round < MAX_ROUNDS:
        current_round += 1
        message_sent = False
        tools = mcp_client_instance.get_tools_definitions()
        
        # --- 1. 调用模型 ---
        try:
            stream = await client.chat.completions.create(
                model=model_settings["Model"],
                messages=message_history,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                stream=True,
                temperature=model_settings["Temperature"],
                extra_body={"enable_thinking": model_settings["Thinking"]} 
            )
        except Exception as e:
            err_msg = f"⚠️ Model API Error: {str(e)}"
            logger.error(err_msg)
            if not message_sent:
                await current_message.send()
            current_message.content += f"\n{err_msg}"
            await current_message.update()
            break

        # [State] 本轮数据缓存
        current_thought = ""
        current_answer = ""
        tool_calls_buffer = {}
        
        # --- 2. 处理流式响应 ---
        async for chunk in stream:
            delta = chunk.choices[0].delta
            
            # A. 收集思考 (Reasoning)
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning and model_settings["Thinking"]:
                current_thought += reasoning
            
            # B. 收集正文 (Content)
            if delta.content:
                current_answer += delta.content
            
            # C. 收集工具调用 (Tool Calls)
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    idx = tool_call.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {
                            "id": tool_call.id,
                            "name": tool_call.function.name or "",
                            "args": tool_call.function.arguments or ""
                        }
                    else:
                        if tool_call.function.name:
                            tool_calls_buffer[idx]["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            tool_calls_buffer[idx]["args"] += tool_call.function.arguments

            # === 渲染逻辑：Markdown 引用块格式 ===
            # 格式： > 思考内容 \n\n 正文内容

            display_parts = []

            if current_thought:
                # 简单处理：给每一行加 >，或者直接全块加 >
                # 为了流式效果好，通常直接前面加 >，换行符替换为 \n>
                formatted_thought = "> " + current_thought.replace("\n", "\n> ")
                display_parts.append(formatted_thought)
            
            if current_answer:
                display_parts.append(current_answer)
            
            full_content = "\n\n".join(display_parts)
            
            if full_content:
                current_message.content = full_content
                if not message_sent:
                    await current_message.send()
                    message_sent = True
                else:
                    await current_message.update()

        # 流结束后的最终状态记录
        full_content = current_message.content
        assistant_msg = {"role": "assistant", "content": current_answer} # 历史记录里只存正文，不存思考过程(可选)
        if current_thought:
            logger.debug(f"\n[🧠 Thinking] {current_thought}")
        if current_answer:
            logger.debug(f"\n[🧸 Answer] {current_answer}")

        # --- 3. 工具调用与循环控制 ---
        if tool_calls_buffer:
            # 整理工具调用参数
            proper_tool_calls = []
            for idx, data in tool_calls_buffer.items():
                proper_tool_calls.append({
                    "id": data["id"],
                    "type": "function",
                    "function": {"name": data["name"], "arguments": data["args"]}
                })

            # 记录 Assistant 消息（带 ToolCall）
            assistant_msg["tool_calls"] = proper_tool_calls
            message_history.append(assistant_msg) 

            # 执行工具
            for tool in proper_tool_calls:
                func_name = tool["function"]["name"]
                call_id = tool["id"]
                args_str = tool["function"]["arguments"]
 
                async with cl.Step(name=func_name, type="tool") as step:
                    step.input = args_str
                    try:
                        args = json.loads(args_str)
                        tool_result = await mcp_client_instance.call_tool(func_name, args)
                        # 确保结果是字符串
                        if not isinstance(tool_result, str):
                            tool_result = json.dumps(tool_result, ensure_ascii=False)
                        step.output = tool_result
                    except Exception as e:
                        tool_result = f"Error: {str(e)}"
                        step.output = tool_result
                        step.is_failed = True

                    message_history.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": func_name,
                        "content": tool_result
                    })

            # 准备下一轮：创建新的消息对象，但不立即发送
            current_message = cl.Message(content="")

        else:
            # 没有工具调用，对话结束
            message_history.append(assistant_msg)
            break
