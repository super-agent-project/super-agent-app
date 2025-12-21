"""
File   : thinking_ui.py
Desc   : 思考过程 UI 组件
Date   : 2025/12/21
Author : Tianyu Chen
"""

import re

# === SVG 图标 ===
RIGHT_ARROW_SVG = """<svg class="ds-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>"""

# === CSS 样式 (V6 间距完美版) ===
DEEPSEEK_CSS = """
<style>
/* --- 容器主样式 --- */
details.deepseek-style {
    background-color: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    margin-bottom: 1rem; /* 外部下间距 */
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

/* --- 标题栏 --- */
details.deepseek-style > summary {
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    font-size: 0.9rem;
    font-weight: 500;
    color: #374151;
    padding: 0.6rem 1rem; /* 稍微调小标题内边距 */
    background-color: #f9fafb;
    transition: background-color 0.2s;
}
details.deepseek-style > summary:hover {
    background-color: #f3f4f6;
}
details.deepseek-style > summary::-webkit-details-marker {
    display: none;
}

/* --- 箭头图标 --- */
.ds-arrow {
    width: 16px;
    height: 16px;
    margin-left: auto;
    color: #9ca3af;
    transition: transform 0.2s ease;
}
details.deepseek-style[open] .ds-arrow {
    transform: rotate(90deg);
}

/* --- 内容区域 --- */
div.ds-content {
    border-top: 1px solid #e5e7eb;
    padding: 0rem 1rem; /* 调整内边距 */
    padding-top: 1rem;
    color: #4b5563;
    font-size: 0.9rem;
}

/* 覆盖 Chainlit/Tailwind 的默认样式 */
div.ds-content p {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    line-height: 1.5 !important;
}
</style>
"""

def clean_text(text: str) -> str:
    return text

def get_thinking_html(content: str) -> str:
    content = clean_text(content)
    display_content = content if content else "思考中..."
    return f"""{DEEPSEEK_CSS}
<details open class="deepseek-style">
<summary>
<span>思考中...</span>
{RIGHT_ARROW_SVG}
</summary>
<div class="ds-content">

{display_content}</div>
</details>
"""

def get_finished_thinking_html(content: str, duration: int) -> str:
    content = clean_text(content)
    if not content:
        return ""
    return f"""{DEEPSEEK_CSS}
<details class="deepseek-style">
<summary>
<span>已思考 (用时 {duration} 秒)</span>
{RIGHT_ARROW_SVG}
</summary>
<div class="ds-content">

{content}</div>
</details>
"""
