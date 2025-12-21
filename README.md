# 🧸 Super Agent

**Slogan**: 打造你的超级 AI 助手！(Build your super AI assistant!)

## 🛠️ 准备环境

### 技术选型

* 编程语言：[Python 3](https://docs.python.org/3/)
* 项目环境和依赖管理：[uv](https://uv.doczh.com/)
* 日志框架：[loguru](https://loguru.readthedocs.io/en/stable/overview.html)
* 单元测试：[pytest](https://docs.pytest.org/en/stable/)
* 项目部署：[docker](https://docs.docker.com/get-started/)
* 模型调用：[OpenAI Python SDK](https://bailian.console.aliyun.com/?spm=a2ty02.30268951.d_model-market.2.67f074a1VkwhFN&tab=api#/api/?type=model&url=2712576)
* AI 应用 UI 框架：[chainlit](https://docs.chainlit.io/get-started/overview)
* 其他依赖随功能迭代继续补充...

### 创建工程

```shell
mkdir super-agent-project && cd super-agent-project
mkdir super-agent-app && cd super-agent-app
```

### 安装依赖

```shell
# 初始化项目
uv init
# 创建虚拟环境（.venv）并添加依赖
uv add loguru pytest pytest-mock openai chainlit
```

**注意❗️**：以上为作者初次安装依赖，其他开发者 clone 项目后，直接在项目路径下运行 `uv sync` 即可。

### 日志策略

* 日志文件路径：logs/app.log
* 日志轮转策略：每周一午夜轮转
* 日志保留策略：6 个月

详见：[src/utils/loguru_utils.py](src/utils/loguru_utils.py)

### 初始化 Chainlit

```shell
chainlit init
```

**注意❗️**：作者已经执行，其他开发者无需再次执行。

### 环境变量

* 作者采用[阿里云百炼平台](https://bailian.console.aliyun.com/?spm=5176.28197581.0.0.12dd29a4fpkfTO&tab=doc#/doc)提供的 LLM 模型服务。
* 执行以下命令前请将 `sk-xxx` 替换为自己的 `API Key`。

```shell
cat > .env << 'EOF'
# 模型配置
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_API_KEY=sk-xxx
EOF
```

**重要‼️**：一定记得在 `.gitignore` 文件中添加 `.env`，以免将其提交到仓库从而导致 `API Key` 泄露。

### 💬 聊天对话：v0.1.0

**相关代码**：

```text
app.py  # 代码入口
  - start_chat()   # 当用户首次打开聊天时触发，获取并存储模型设置
  - setup_agent()  # 当用户更新设置时触发，更新聊天模型设置
  - main()         # 当用户发送消息时触发，处理用户消息并生成响应

src  # 核心源码
  - agent
      - chat_agent   # 聊天智能体，支持流式和阻塞式响应，支持思考模式
  - ui
      - thinking_ui  # 个性化思考过程 UI 组件
  - utils
      - loguru_utils              # loguru 日志工具
          - config_loguru()           # 初始化日志配置
      - chainlit_utils            # chainlit 工具
          - get_model_settings()      # 获取聊天模型设置，如模型、流式输出、深度思考、角色设定等

public  # 个性化设置
  - favicon.png     # 个性化网页图标
  - logo_light.png  # 浅色主题下的个性化网站 logo
  - logo_dark.png   # 深色主题下的个性化网站 logo
  - theme.json      # 主题设置
      - "--primary": "221.2 83.2% 53.3%"  # 主色调改为蓝色（浅色和深色主题都要改）
      - "--ring": "221.2 83.2% 53.3%"     # 聚焦环改为蓝色（浅色和深色主题都要改）

.chainlit  # chainlit 配置
  - config.toml     # chainlit 配置文件
      - [UI]            # UI 相关配置
          - name = "SuperAgent"               # 设置网站名称
          - default_theme = "light"           # 默认为浅色主题
          - description = "你的超级 AI 助手。"   # 网站描述
          - language = "zh-CN"                # 默认语言为中文
      - [features]      # 功能配置
          - unsafe_allow_html = true          # 消息中启用 HTML 显示（以允许个性化思考过程 UI 样式）
  - translations
      - zh-CN.json  # 中文相关配置
          - watermark   # 修改脚注为“内容由 AI 生成，请仔细甄别”
```

**启动项目**：

```shell
# 开发模式（自动检测代码更新）
chainlit run app.py -w

# 正式环境
uv run chainlit run app.py
```

**测试对话**：

![主页面](./images/01_主页面.png)

![设置面板](./images/02_设置面板.png)

![对话](./images/03_对话.png)
