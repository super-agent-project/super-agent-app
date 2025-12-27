"""
File   : cmd_utils.py
Desc   : 命令行解析
Date   : 2025/12/27
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

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.mcp_client import mcp_client_instance


async def parse_help_cmd(user_input: str) -> bool:
    """
    帮助命令 (/help)
    """

    help_content="""
**Available Commands!**

- Use `@folders` to see available topics
- Use `@<topic>` to search papers in that topic
- Use `/prompts` to list available prompts
- Use `/prompt <name> <arg1=value1>` to execute a prompt
"""
    user_input = user_input.strip()
    if user_input.startswith("/help"):
        await cl.Message(content=help_content).send()
        return True
    return False


async def parse_resource_cmd(user_input: str) -> bool:
    """
    资源查看命令 (@resource)
    """

    user_input = user_input.strip()
    if user_input.startswith("@"):
        uri_suffix = user_input[1:].strip()
        uri = "papers://folders" if uri_suffix == "folders" else f"papers://{uri_suffix}"
        
        async with cl.Step(name="Fetch Resource") as step:
            step.input = uri
            try:
                content = await mcp_client_instance.read_resource(uri)
                step.output = content[:500] + "..." if len(content) > 500 else content
            except Exception as e:
                step.output = f"❌ Error reading resource: {str(e)}"
        
        await cl.Message(content=f"📄 **Resource Content**:\n\n{content}\n").send()
        return True
    return False


async def parse_prompts_cmd(user_input: str) -> bool:
    """
    列出 prompts 命令 (/prompts)
    """

    user_input = user_input.strip()
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
        return True
    return False


async def parse_prompt_cmd(user_input: str) -> str | None:
    """
    执行 prompt 命令 (/prompt)
    """

    user_input = user_input.strip()
    if user_input.startswith("/prompt"):
        # try-except 用于捕获引号不匹配的情况（比如只写了一个 "）
        try:
            # 使用 shlex.split 来解析参数
            parts = shlex.split(user_input)
        except ValueError as e:
            await cl.Message(content=f"⚠️ 参数解析错误: 引号未闭合 ({e})").send()
            return None

        if len(parts) < 2:
            await cl.Message(content="用法: `/prompt <name> <arg1=value1> ...`").send()
            return None

        prompt_name = parts[1]
        args = {}

        # 遍历解析后的部分
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
                return None
            return final_input
    return ""
