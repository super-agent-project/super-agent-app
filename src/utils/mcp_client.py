import os
import json
import asyncio
from contextlib import AsyncExitStack
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Prompt

# 分隔符配置
SPLIT_SERVER_TOOL_NAME_WITH = "-"

class MCPClientManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPClientManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        self.exit_stack = AsyncExitStack()
        
        # 核心存储：映射 名称/URI -> Session
        self.sessions: Dict[str, ClientSession] = {} 
        
        # 功能注册表
        self.tool_definitions: List[Dict] = []  # OpenAI 格式
        self.available_prompts: List[Dict] = [] # 简单描述格式
        self.available_resources: List[str] = [] # URI 列表
        
        self.initialized = True

    async def initialize(self, config_path: str = "configs/server_config.json"):
        """初始化连接并加载所有能力（Tools, Prompts, Resources）"""
        try:
            if not os.path.exists(config_path):
                logger.error(f"Config file not found: {config_path}")
                return

            logger.info(f"Loading config from {config_path}")
            with open(config_path, "r") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            for server_name, server_config in servers.items():
                await self._connect_to_server(server_name, server_config)
            
            logger.success(f"MCP Client Ready. Tools: {len(self.tool_definitions)}, Prompts: {len(self.available_prompts)}, Resources: {len(self.available_resources)}")
            
        except Exception as e:
            logger.exception(f"Error loading server config: {e}")
            raise

    async def _connect_to_server(self, server_name: str, server_config: dict):
        """连接到单个 MCP 服务器并注册其能力"""
        try:
            read, write = None, None
            
            # 1. 建立传输层
            if 'url' in server_config:
                url = server_config['url']
                if 'sse' in url:
                    logger.debug(f"Connecting to {server_name} via SSE: {url}")
                    sse_transport = await self.exit_stack.enter_async_context(
                        sse_client(url=url)
                    )
                    read, write = sse_transport
                elif 'mcp' in url:
                    logger.debug(f"Connecting to {server_name} via Streamable HTTP: {url}")
                    streamable_transport = await self.exit_stack.enter_async_context(
                        streamablehttp_client(url=url)
                    )
                    read, write, *_ = streamable_transport
            else:
                logger.debug(f"Connecting to {server_name} via Stdio")
                server_params = StdioServerParameters(**server_config)
                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                read, write = stdio_transport

            # 2. 初始化 Session
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()

            # 3. 注册所有能力
            await self._register_capabilities(server_name, session)
            
        except Exception as e:
            logger.error(f"Failed to connect to server '{server_name}': {e}")

    async def _register_capabilities(self, server_name: str, session: ClientSession):
        """一次性注册 Tools, Prompts, Resources"""
        
        # --- Tools ---
        try:
            tools_resp = await session.list_tools()
            for tool in tools_resp.tools:
                full_name = f"{server_name}{SPLIT_SERVER_TOOL_NAME_WITH}{tool.name}"
                self.sessions[full_name] = session # 注册 Tool 路由
                
                input_schema = tool.inputSchema if tool.inputSchema else {}
                self.tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": full_name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": input_schema.get('properties', {}),
                            "required": input_schema.get('required', [])
                        }
                    }
                })
        except Exception as e:
            logger.warning(f"[{server_name}] Failed to list tools: {e}")

        # --- Prompts ---
        try:
            prompts_resp = await session.list_prompts()
            if prompts_resp and prompts_resp.prompts:
                for prompt in prompts_resp.prompts:
                    self.available_prompts.append({
                        "name": prompt.name,
                        "description": prompt.description,
                        "arguments": prompt.arguments,
                        "server": server_name
                    })
                    # 将 Prompt 名字也注册到 Session，方便查找
                    self.sessions[f"prompt:{prompt.name}"] = session
        except Exception:
            pass # 某些 Server 可能不支持 Prompts

        # --- Resources ---
        try:
            res_resp = await session.list_resources()
            if res_resp and res_resp.resources:
                for resource in res_resp.resources:
                    uri_str = str(resource.uri)
                    self.available_resources.append(uri_str)
                    # 将 URI 注册到 Session
                    self.sessions[uri_str] = session
        except Exception:
            pass # 某些 Server 可能不支持 Resources

    # ================= 对外接口 =================

    def get_tools_definitions(self) -> List[Dict]:
        """获取 OpenAI 格式的工具定义"""
        return self.tool_definitions

    def get_available_prompts(self) -> List[Dict]:
        """获取所有可用 Prompt 列表"""
        return self.available_prompts

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """执行工具"""
        if tool_name not in self.sessions:
            raise ValueError(f"Tool {tool_name} not found.")

        session = self.sessions[tool_name]
        real_tool_name = tool_name.split(SPLIT_SERVER_TOOL_NAME_WITH, 1)[1] if SPLIT_SERVER_TOOL_NAME_WITH in tool_name else tool_name

        try:
            logger.info(f"Executing tool: {real_tool_name} args: {arguments}")
            result = await session.call_tool(name=real_tool_name, arguments=arguments)
            
            content = []
            if result.content:
                for item in result.content:
                    if hasattr(item, 'text'):
                        content.append(item.text)
                    else:
                        content.append(str(item))
            return "\n".join(content)
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return f"Error: {str(e)}"

    async def get_prompt(self, prompt_name: str, arguments: dict) -> str:
        """执行/获取 Prompt 模板内容"""
        # 查找对应的 session
        session = self.sessions.get(f"prompt:{prompt_name}")
        if not session:
            return f"Prompt '{prompt_name}' not found."

        try:
            logger.info(f"Fetching prompt: {prompt_name}")
            result = await session.get_prompt(name=prompt_name, arguments=arguments)
            if result and result.messages:
                # 简单处理：将 Prompt 的所有消息内容合并为一个字符串返回
                # 实际场景中可能直接返回 messages 列表给 LLM，这里为了通用性转为文本
                return "\n".join([msg.content.text for msg in result.messages if hasattr(msg.content, 'text')])
            return ""
        except Exception as e:
            logger.error(f"Failed to get prompt: {e}")
            return str(e)

    async def read_resource(self, uri: str) -> str:
        """读取资源内容"""
        session = self.sessions.get(uri)
        
        # 模糊匹配 Session (例如 papers://folders 可能没有精确注册，但 papers:// 在)
        if not session:
            for known_key, sess in self.sessions.items():
                if uri.startswith(known_key) or ("://" in known_key and uri.startswith(known_key.split("://")[0])):
                    session = sess
                    break
        
        if not session:
            return f"Resource not found: {uri}"

        try:
            logger.info(f"Reading resource: {uri}")
            result = await session.read_resource(uri=uri)
            if result and result.contents:
                return result.contents[0].text
            return "Empty resource."
        except Exception as e:
            logger.error(f"Failed to read resource: {e}")
            return str(e)

    async def cleanup(self):
        await self.exit_stack.aclose()
        logger.info("Connections closed.")

# 全局单例
mcp_client_instance = MCPClientManager()
