#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown to WeChat Public Account HTML Converter

将 Markdown 文件转换为微信公众号兼容的 HTML 格式。
支持多种风格模板，代码块缩进保留，图片 base64 嵌入。
"""

import re
import os
import base64
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import requests


@dataclass
class StyleConfig:
    """风格配置类"""
    name: str
    # 标题条样式
    header_bg_color: str = "#3C3C3C"
    header_text_color: str = "#FFFFFF"
    header_font_size: str = "20px"
    # 主卡片样式
    card_bg_color: str = "#FFFFFF"
    card_border_color: str = "#D9D9D9"
    card_text_color: str = "#333333"
    # H2/H3 卡片样式（用于包裹H2/H3标题后的内容）
    h2_h3_card_bg_color: str = "rgba(250, 250, 250, 0.4)"  # 支持rgba格式
    h2_h3_card_border_color: str = "#E8E8E8"
    # H2 标题样式（粗横线中间为标题）
    h2_title_line_color: str = "#333333"
    h2_title_text_color: str = "#333333"
    h2_title_font_size: str = "18px"
    # H3 标题样式（卡片式）
    h3_title_bg_color: str = "#F5F5F5"
    h3_title_border_color: str = "#3C3C3C"
    h3_title_text_color: str = "#333333"
    h3_title_font_size: str = "16px"
    # 代码块样式
    code_bg_color: str = "#F4F4F4"
    code_border_color: str = "#E0E0E0"
    # 元信息样式
    meta_text_color: str = "#888888"
    meta_font_size: str = "12px"
    # 来源样式
    source_text_color: str = "#999999"
    source_font_size: str = "12px"


# 预定义风格
STYLES = {
    "academic_gray": StyleConfig(
        name="学术灰风格",
        header_bg_color="#3C3C3C",
        header_text_color="#FFFFFF",
        header_font_size="20px",
        card_bg_color="#FFFFFF",
        card_border_color="#D9D9D9",
        card_text_color="#333333",
        h2_h3_card_bg_color="rgba(250, 250, 250, 0.4)",
        h2_h3_card_border_color="#E8E8E8",
        h2_title_line_color="#333333",
        h2_title_text_color="#333333",
        h2_title_font_size="18px",
        h3_title_bg_color="#F5F5F5",
        h3_title_border_color="#3C3C3C",
        h3_title_text_color="#333333",
        h3_title_font_size="16px",
        code_bg_color="#F4F4F4",
        code_border_color="#E0E0E0",
        meta_text_color="#888888",
        meta_font_size="12px",
        source_text_color="#999999",
        source_font_size="12px",
    ),
    "festival": StyleConfig(
        name="节日快乐色彩系",
        header_bg_color="#FF6B6B",  # 温暖的红色
        header_text_color="#FFFFFF",
        header_font_size="20px",
        card_bg_color="#FFF8E1",  # 温暖的米白色
        card_border_color="#FFB74D",  # 金色边框
        card_text_color="#5D4037",  # 深棕色文字
        h2_h3_card_bg_color="rgba(255, 235, 59, 0.3)",  # 淡金色背景
        h2_h3_card_border_color="#FFB74D",  # 金色边框
        h2_title_line_color="#FF6B6B",  # 红色横线
        h2_title_text_color="#D32F2F",  # 深红色标题
        h2_title_font_size="18px",
        h3_title_bg_color="#FFE082",  # 淡金色背景
        h3_title_border_color="#FF6B6B",  # 红色左边框
        h3_title_text_color="#D32F2F",  # 深红色文字
        h3_title_font_size="16px",
        code_bg_color="#FFF3E0",  # 温暖的橙色背景
        code_border_color="#FFB74D",
        meta_text_color="#8D6E63",
        meta_font_size="12px",
        source_text_color="#A1887F",
        source_font_size="12px",
    ),
    "tech": StyleConfig(
        name="科技产品介绍色彩系",
        header_bg_color="#1565C0",  # 科技蓝
        header_text_color="#FFFFFF",
        header_font_size="20px",
        card_bg_color="#E3F2FD",  # 淡蓝色背景
        card_border_color="#42A5F5",  # 蓝色边框
        card_text_color="#0D47A1",  # 深蓝色文字
        h2_h3_card_bg_color="rgba(66, 165, 245, 0.2)",  # 淡蓝色背景
        h2_h3_card_border_color="#42A5F5",  # 蓝色边框
        h2_title_line_color="#1565C0",  # 深蓝色横线
        h2_title_text_color="#0D47A1",  # 深蓝色标题
        h2_title_font_size="18px",
        h3_title_bg_color="#BBDEFB",  # 淡蓝色背景
        h3_title_border_color="#1565C0",  # 深蓝色左边框
        h3_title_text_color="#0D47A1",  # 深蓝色文字
        h3_title_font_size="16px",
        code_bg_color="#E1F5FE",  # 青色背景
        code_border_color="#26C6DA",
        meta_text_color="#546E7A",
        meta_font_size="12px",
        source_text_color="#78909C",
        source_font_size="12px",
    ),
    "announcement": StyleConfig(
        name="重大事情告知色彩系",
        header_bg_color="#D32F2F",  # 警示红色
        header_text_color="#FFFFFF",
        header_font_size="22px",
        card_bg_color="#FFF3E0",  # 淡橙色背景
        card_border_color="#FF5722",  # 深橙色边框
        card_text_color="#BF360C",  # 深橙色文字
        h2_h3_card_bg_color="rgba(255, 152, 0, 0.25)",  # 淡橙色背景
        h2_h3_card_border_color="#FF5722",  # 橙色边框
        h2_title_line_color="#D32F2F",  # 红色横线
        h2_title_text_color="#BF360C",  # 深橙色标题
        h2_title_font_size="20px",
        h3_title_bg_color="#FFE0B2",  # 淡橙色背景
        h3_title_border_color="#D32F2F",  # 红色左边框
        h3_title_text_color="#BF360C",  # 深橙色文字
        h3_title_font_size="17px",
        code_bg_color="#FFEBEE",  # 淡红色背景
        code_border_color="#EF5350",
        meta_text_color="#8D6E63",
        meta_font_size="12px",
        source_text_color="#A1887F",
        source_font_size="12px",
    ),
}


class MarkdownParser:
    """Markdown 解析器"""
    
    def __init__(self, md_content: str):
        self.content = md_content
        self.front_matter = {}
        self.body = ""
        self._parse_front_matter()
    
    def _parse_front_matter(self):
        """解析 front matter (YAML 格式)"""
        if not self.content.startswith("---"):
            self.body = self.content
            return
        
        # 查找 front matter 结束位置
        lines = self.content.split("\n")
        if lines[0].strip() != "---":
            self.body = self.content
            return
        
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        
        if end_idx == -1:
            self.body = self.content
            return
        
        # 解析 front matter
        fm_lines = lines[1:end_idx]
        i = 0
        while i < len(fm_lines):
            line = fm_lines[i].strip()
            if not line:
                i += 1
                continue
            
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # 检查是否是列表（多行格式）
                if i + 1 < len(fm_lines) and fm_lines[i + 1].strip().startswith("-"):
                    # 多行列表
                    items = []
                    i += 1
                    while i < len(fm_lines) and fm_lines[i].strip().startswith("-"):
                        item = fm_lines[i].strip()[1:].strip().strip('"').strip("'")
                        items.append(item)
                        i += 1
                    value = items
                    i -= 1  # 回退一步，因为外层循环会 +1
                elif value.startswith("["):
                    # 行内列表
                    items = re.findall(r"-?\s*([^\]]+)", value)
                    value = [item.strip().strip('"').strip("'") for item in items if item.strip()]
                
                self.front_matter[key] = value
            
            i += 1
        
        # 提取 body
        self.body = "\n".join(lines[end_idx + 1:])
    
    def get_front_matter(self, key: str, default: any = None) -> any:
        """获取 front matter 值"""
        return self.front_matter.get(key, default)


class CodeBlockFormatter:
    """代码块格式化器 - 使用 <br> + &nbsp; 方法保留缩进，支持语法高亮"""
    
    def __init__(self, style_config: Optional[StyleConfig] = None):
        """
        Args:
            style_config: 样式配置（可选）
        """
        self.style_config = style_config
    
    def format_code_block(self, code: str, language: str = "", show_line_numbers: bool = True) -> str:
        """
        公众号安全：逐行 <span> + &nbsp; 不换行，超宽横向滚动；不插入零宽字符，复制到 IDE 安全
        
        Args:
            code: 代码内容
            language: 语言标识（可选）
            show_line_numbers: 是否显示行号（默认 True）
        
        Returns:
            格式化后的 HTML
        """
        import html
        
        code = code.rstrip("\n")
        lines = code.split("\n")
        if not lines:
            return ""

        # 计算行号宽度
        n = len(lines)
        lnw = len(str(n)) if show_line_numbers else 0

        # 语法高亮（可选，失败则回退）
        # 优先使用自定义的 InlineStyleFormatter（如果可用），否则使用标准 HtmlFormatter
        highlighted_lines = None
        if language:
            try:
                from pygments import highlight
                from pygments.lexers import get_lexer_by_name
                from pygments.util import ClassNotFound
                
                lexer = get_lexer_by_name(language, stripall=False)
                
                # 优先尝试使用自定义的 InlineStyleFormatter（输出格式更可控）
                try:
                    try:
                        from .inline_formatter import InlineStyleFormatter
                    except ImportError:
                        from inline_formatter import InlineStyleFormatter
                    formatter = InlineStyleFormatter()
                    html_all = highlight(code, lexer, formatter)
                except (ImportError, Exception):
                    # 回退到标准 HtmlFormatter
                    from pygments.formatters import HtmlFormatter
                    fmt = HtmlFormatter(noclasses=True, nowrap=True)
                    html_all = highlight(code, lexer, fmt)
                
                # 统一换行（Pygments 可能输出 <span>...<br>）
                html_all = html_all.replace("\r\n", "\n").replace("\r", "\n")
                
                # 移除 Pygments 可能添加的包装标签
                # HtmlFormatter 可能输出 <div class="highlight"><pre>...</pre></div>
                import re
                # 移除 <div> 包装
                html_all = re.sub(r'<div[^>]*>', '', html_all)
                html_all = html_all.replace('</div>', '')
                # 移除 <pre> 标签
                html_all = html_all.replace('<pre>', '').replace('</pre>', '')
                # 移除可能的 <style> 标签（Pygments 可能添加）
                html_all = re.sub(r'<style[^>]*>.*?</style>', '', html_all, flags=re.DOTALL)
                
                # 按 <br> 或换行符分割
                if '<br>' in html_all:
                    highlighted_lines = html_all.split('<br>')
                else:
                    highlighted_lines = html_all.split("\n")
                
                # 移除每行首尾的空白字符
                highlighted_lines = [line.strip() for line in highlighted_lines]
                
                # 兜底：行数对不上就放弃高亮
                if len(highlighted_lines) != len(lines):
                    highlighted_lines = None
            except (ClassNotFound, ImportError, Exception):
                # 如果高亮失败，静默回退到纯文本
                highlighted_lines = None

        # 逐行构造：空格->&nbsp;，Tab -> 4个&nbsp;
        def to_nbsp(s: str) -> str:
            s = s.replace("\t", "    ")
            # 对纯文本需要转义；若用了高亮，就不再额外转义那一行的标签
            return s.replace(" ", "&nbsp;")

        html_lines = []
        for i, raw in enumerate(lines, 1):
            if highlighted_lines is not None and i <= len(highlighted_lines):
                # 这行已经带 <span style=...> 标签了：只把裸空格变成&nbsp;，不要再全局 html.escape
                line_inner = highlighted_lines[i-1].replace("\t", "    ").replace(" ", "&nbsp;")
            else:
                # 纯文本：先转义，再空格替换
                line_inner = to_nbsp(html.escape(raw))

            if show_line_numbers:
                ln = str(i).rjust(lnw, " ")
                ln = ln.replace(" ", "&nbsp;")
                # 行号与代码分两块，整体 nowrap
                html_line = (
                    f'<span style="display:block;white-space:nowrap;">'
                    f'<span style="color:#999;display:inline-block;width:{lnw + 1}em;text-align:right;padding-right:0.8em;user-select:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;">{ln}</span>&nbsp;{line_inner}'
                    f'</span>'
                )
            else:
                html_line = f'<span style="display:block;white-space:nowrap;">{line_inner}</span>'

            html_lines.append(html_line)

        code_bg = self.style_config.code_bg_color if self.style_config else "#F4F4F4"
        code_bd = self.style_config.code_border_color if self.style_config else "#E0E0E0"

        # 外容器不使用 <pre>，避免被清洗；使用横向滚动 + 等宽字体
        # 这里不用 white-space:pre；逐行 span 已经 nowrap，复制安全
        return (
            f'<p style="background-color:{code_bg};'
            f'border:1px solid {code_bd};border-radius:8px;'
            f'font-family:Consolas,Menlo,Monaco,monospace;'
            f'overflow-x:auto;-webkit-overflow-scrolling:touch;'
            f'padding:10px;line-height:1.6;margin:10px 0;">\n'
            + "\n".join(html_lines) +
            '\n</p><br>'
        )
    
    @staticmethod
    def _insert_zero_width_chars(text: str) -> str:
        """
        在文本字符之间插入零宽字符，破坏微信的自动分词逻辑
        使用零宽不连字（U+200C）和零宽空格（U+200B）交替插入
        在每个字符之间插入（包括空格），确保完全破坏分词逻辑
        """
        ZERO_WIDTH_NON_JOINER = '\u200C'  # 零宽不连字
        ZERO_WIDTH_SPACE = '\u200B'  # 零宽空格
        
        result = []
        i = 0
        in_tag = False
        in_entity = False
        zw_char_index = 0  # 用于交替使用两种零宽字符
        
        while i < len(text):
            char = text[i]
            
            # 检测HTML标签
            if char == '<':
                in_tag = True
                result.append(char)
            elif char == '>':
                in_tag = False
                result.append(char)
            # 检测HTML实体（如 &nbsp; &amp; 等）
            elif char == '&' and not in_tag:
                in_entity = True
                result.append(char)
            elif char == ';' and in_entity:
                # HTML实体结束，在实体后面插入零宽字符
                in_entity = False
                result.append(char)
                # 在HTML实体后面也插入零宽字符，确保实体之间也有零宽字符
                if i + 1 < len(text):
                    next_char = text[i + 1]
                    if next_char not in ['<', '>']:
                        zw_char = ZERO_WIDTH_NON_JOINER if zw_char_index % 2 == 0 else ZERO_WIDTH_SPACE
                        result.append(zw_char)
                        zw_char_index += 1
            else:
                # 普通字符（包括空格、换行等所有字符）
                result.append(char)
                # 如果不在标签和实体中，在每个字符后面都插入零宽字符
                if not in_tag and not in_entity:
                    # 检查下一个字符，确保不是标签开始或实体开始
                    if i + 1 < len(text):
                        next_char = text[i + 1]
                        # 如果下一个字符不是 < > &，则插入零宽字符
                        # 这样可以确保所有可见字符之间都有零宽字符，破坏微信的分词逻辑
                        if next_char not in ['<', '>', '&']:
                            # 交替使用零宽不连字和零宽空格，增强效果
                            zw_char = ZERO_WIDTH_NON_JOINER if zw_char_index % 2 == 0 else ZERO_WIDTH_SPACE
                            result.append(zw_char)
                            zw_char_index += 1
                        # 如果下一个字符是 &（实体开始），也在当前字符后插入零宽字符
                        elif next_char == '&':
                            zw_char = ZERO_WIDTH_NON_JOINER if zw_char_index % 2 == 0 else ZERO_WIDTH_SPACE
                            result.append(zw_char)
                            zw_char_index += 1
            
            i += 1
        
        return ''.join(result)
    
    def _format_plain_code(self, code: str, lines: List[str], min_indent: int) -> str:
        """格式化纯文本代码（无语法高亮）"""
        formatted_lines = []
        for line in lines:
            if not line.strip():
                # 空行
                formatted_lines.append("<br>")
            else:
                # 计算相对缩进
                leading_spaces = 0
                for char in line:
                    if char == ' ':
                        leading_spaces += 1
                    elif char == '\t':
                        leading_spaces += 4
                    else:
                        break
                
                relative_indent = leading_spaces - min_indent
                if relative_indent < 0:
                    relative_indent = 0
                
                # 先插入零宽字符到原始文本，破坏微信的自动分词逻辑
                # 这样可以在空格转换为&nbsp;之前就插入零宽字符
                line_with_zw = self._insert_zero_width_chars(line.lstrip())
                
                # 转义 HTML 特殊字符，并将所有空格转换为 &nbsp; 以保留空格
                # 注意：零宽字符不会影响转义和空格转换
                escaped_line = (line_with_zw
                              .replace("&", "&amp;")
                              .replace("<", "&lt;")
                              .replace(">", "&gt;")
                              .replace('"', "&quot;")
                              .replace("'", "&#39;")
                              .replace(" ", "&nbsp;"))  # 将所有空格转换为 &nbsp;
                
                # 添加缩进（每个空格用 1 个 &nbsp;）
                indent_html = "&nbsp;" * relative_indent
                # 每行代码用span包裹并设置white-space:nowrap，强制不换行
                # 配合外层p标签的white-space:pre和overflow-x:auto，双重保障防止换行
                formatted_lines.append(f'<span style="white-space:nowrap;">{indent_html}{escaped_line}</span><br>')
        
        return "".join(formatted_lines)
    
    def _apply_indentation_to_highlighted(self, highlighted_html: str, original_lines: List[str], min_indent: int) -> str:
        """为已高亮的 HTML 代码添加缩进"""
        # 将高亮的 HTML 按 <br> 分割成行
        parts = highlighted_html.split('<br>')
        
        formatted_parts = []
        line_idx = 0
        
        def replace_spaces_in_text(text: str) -> str:
            """将文本中的空格转换为 &nbsp;，但不影响HTML标签"""
            # 使用正则表达式，只替换不在HTML标签内的空格
            # 匹配模式：空格前后都不在HTML标签内
            # 方法：先找到所有HTML标签的位置，然后只替换标签外的空格
            result = []
            i = 0
            in_tag = False
            
            while i < len(text):
                if text[i] == '<':
                    in_tag = True
                    result.append(text[i])
                elif text[i] == '>':
                    in_tag = False
                    result.append(text[i])
                elif text[i] == ' ' and not in_tag:
                    # 不在标签内的空格，转换为 &nbsp;
                    result.append('&nbsp;')
                else:
                    result.append(text[i])
                i += 1
            
            return ''.join(result)
        
        for part in parts:
            if line_idx < len(original_lines):
                line = original_lines[line_idx]
                if line.strip():
                    # 计算相对缩进
                    leading_spaces = 0
                    for char in line:
                        if char == ' ':
                            leading_spaces += 1
                        elif char == '\t':
                            leading_spaces += 4
                        else:
                            break
                    
                    relative_indent = leading_spaces - min_indent
                    if relative_indent < 0:
                        relative_indent = 0
                    
                    # 将高亮HTML中的空格转换为 &nbsp;（保留HTML标签）
                    part_with_spaces = replace_spaces_in_text(part)
                    
                    # 在字符之间插入零宽字符，破坏微信的自动分词逻辑
                    part_with_spaces = self._insert_zero_width_chars(part_with_spaces)
                    
                    # 添加缩进（在每行的开始，每个空格用 1 个 &nbsp;）
                    indent_html = "&nbsp;" * relative_indent
                    # 每行代码用span包裹并设置white-space:nowrap，强制不换行
                    formatted_parts.append(f'<span style="white-space:nowrap;">{indent_html}{part_with_spaces}</span>')
                else:
                    # 空行也用span包裹，保持结构一致
                    formatted_parts.append('<span style="white-space:nowrap;">&nbsp;</span>')
                line_idx += 1
            else:
                formatted_parts.append(part)
            
            # 添加换行（除了最后一部分）
            if line_idx < len(original_lines) or part != parts[-1]:
                formatted_parts.append('<br>')
        
        return "".join(formatted_parts)
    
    def _add_line_numbers(self, code_html: str, original_lines: List[str], line_number_width: int) -> str:
        """为代码 HTML 添加行号"""
        # 行号宽度：根据总行数计算，增加宽度以确保两位数及以上不会挤下去
        # 1-9行：3em, 10-99行：3.5em, 100-999行：4em, 1000+行：4.5em
        if line_number_width <= 1:
            width = "3em"  # 增加基础宽度
        elif line_number_width == 2:
            width = "3.5em"  # 两位数使用更宽的宽度
        elif line_number_width == 3:
            width = "4em"  # 三位数
        else:
            width = "4.5em"  # 四位数及以上
        
        # 行号样式：灰色、右对齐、固定宽度，不可选择
        line_number_style = f"display:inline-block;width:{width};text-align:right;padding-right:0.8em;color:#999;user-select:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;"
        
        # 将代码 HTML 按 <br> 分割成行
        code_lines = code_html.split('<br>')
        
        # 确保行数匹配（处理最后可能没有 <br> 的情况）
        # 移除最后一个空元素（如果有）
        if code_lines and code_lines[-1] == '':
            code_lines = code_lines[:-1]
        
        # 确保行数不超过原始行数
        if len(code_lines) > len(original_lines):
            code_lines = code_lines[:len(original_lines)]
        
        # 为每一行添加行号
        lines_with_numbers = []
        for idx, code_line in enumerate(code_lines):
            line_num = idx + 1
            # 在行号数字之间插入零宽字符，破坏微信的自动分词逻辑
            line_num_str = str(line_num)
            line_num_with_zw = self._insert_zero_width_chars(line_num_str)
            # 添加行号（每行开头）
            line_number_html = f'<span style="{line_number_style}">{line_num_with_zw}</span>'
            # 将行号和代码行一起包裹在span中，设置white-space:nowrap强制不换行
            # 确保整行（行号+代码）作为一个整体不换行
            lines_with_numbers.append(f'<span style="white-space:nowrap;">{line_number_html}{code_line}</span><br>')
        
        return "".join(lines_with_numbers)


class FormulaProcessor:
    """数学公式处理器 - 本地渲染为图片并转为 base64"""
    
    def __init__(self, temp_dir: Optional[str] = None, cleanup: bool = True, style_config: Optional[StyleConfig] = None):
        """
        Args:
            temp_dir: 临时文件目录（默认：系统临时目录）
            cleanup: 是否在转换完成后清理临时文件
            style_config: 样式配置（用于适配主题背景色）
        """
        import tempfile
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "md2wechat_formulas"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup = cleanup
        self.temp_files = []  # 记录临时文件，用于清理
        self.style_config = style_config
    
    @staticmethod
    def _is_light_color(color: str) -> bool:
        """
        判断颜色是否为亮色
        
        Args:
            color: 颜色字符串（支持 #RRGGBB, rgb(r,g,b), rgba(r,g,b,a) 格式）
        
        Returns:
            True 如果为亮色，False 如果为暗色
        """
        import re
        
        # 解析颜色值
        r, g, b = 255, 255, 255  # 默认白色
        
        # 处理 #RRGGBB 格式
        hex_match = re.match(r'^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$', color)
        if hex_match:
            r = int(hex_match.group(1), 16)
            g = int(hex_match.group(2), 16)
            b = int(hex_match.group(3), 16)
        else:
            # 处理 rgba(r, g, b, a) 或 rgb(r, g, b) 格式
            rgba_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)', color)
            if rgba_match:
                r = int(rgba_match.group(1))
                g = int(rgba_match.group(2))
                b = int(rgba_match.group(3))
        
        # 计算亮度（使用相对亮度公式）
        # Y = 0.299*R + 0.587*G + 0.114*B
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        
        # 如果亮度大于 128，认为是亮色
        return brightness > 128
    
    @staticmethod
    def _convert_cases_to_array(latex: str) -> str:
        """
        将 LaTeX 的 cases 环境转换为 array 环境（CodeCogs 不支持 cases）
        
        Args:
            latex: 原始 LaTeX 代码
        
        Returns:
            转换后的 LaTeX 代码
        """
        import re
        
        # 匹配 \begin{cases}...\end{cases}
        # 注意：cases 环境中的内容可能包含换行和逗号
        pattern = r'\\begin\{cases\}(.*?)\\end\{cases\}'
        
        def replace_cases(match):
            content = match.group(1)
            # 移除首尾空白
            content = content.strip()
            
            # 分割内容为多行（只在 \\ 或 \\\\ 处分割，这是 LaTeX 换行符）
            # 使用 + 匹配一个或多个连续的 \\
            lines = re.split(r'\\\\+', content)
            # 过滤空行
            lines = [line.strip() for line in lines if line.strip()]
            
            # 构建 array 环境
            # 格式：\left\{\begin{array}{ll}...\end{array}\right.
            array_lines = []
            for i, line in enumerate(lines):
                # 处理每行，格式通常是：值,条件, 或 值,条件
                # 例如：0,x<a, -> 0 & x<a
                # 先去掉末尾的逗号（如果有）
                line = line.rstrip(',').strip()
                
                # 在第一个逗号处分割（值,条件）
                if ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        value, condition = parts[0].strip(), parts[1].strip()
                        # 将 \lt 和 \ge 等转换为标准的 < 和 >=（CodeCogs 可能不支持某些命令）
                        # 注意：这里需要保留 LaTeX 命令，但可能需要转换某些特殊命令
                        array_lines.append(f"{value} & {condition}")
                    else:
                        array_lines.append(line)
                else:
                    array_lines.append(line)
                
                # 除了最后一行，添加 \\
                if i < len(lines) - 1:
                    array_lines.append('\\\\')
            
            array_content = ' '.join(array_lines)
            return f'\\left\\{{\\begin{{array}}{{ll}}{array_content}\\end{{array}}\\right.'
        
        # 替换所有 cases 环境
        result = re.sub(pattern, replace_cases, latex, flags=re.DOTALL)
        
        # CodeCogs 不支持 \lt，需要转换为 <
        # 注意：只替换独立的 \lt，不替换 \delta 等其他命令中的 lt
        result = re.sub(r'\\lt(?![a-zA-Z])', '<', result)
        
        return result
    
    @staticmethod
    def _add_html_noise(html: str) -> str:
        """
        为HTML添加噪声，包括零宽字符、随机空格等，以避免被微信公众号过滤
        
        Args:
            html: 原始HTML字符串
        
        Returns:
            添加噪声后的HTML字符串
        """
        import random
        
        ZERO_WIDTH_NON_JOINER = '\u200C'  # 零宽不连字
        ZERO_WIDTH_SPACE = '\u200B'  # 零宽空格
        ZERO_WIDTH_JOINER = '\u200D'  # 零宽连字
        
        result = []
        i = 0
        in_tag = False
        in_quotes = False
        quote_char = None
        zw_chars = [ZERO_WIDTH_NON_JOINER, ZERO_WIDTH_SPACE, ZERO_WIDTH_JOINER]
        # 跟踪最近几个字符，避免在关键位置插入零宽字符
        recent_chars = []
        
        while i < len(html):
            char = html[i]
            recent_chars.append(char)
            if len(recent_chars) > 5:
                recent_chars.pop(0)
            
            # 检测HTML标签
            if char == '<' and not in_quotes:
                in_tag = True
                result.append(char)
            elif char == '>' and not in_quotes:
                in_tag = False
                result.append(char)
                # 在标签结束后随机插入零宽字符（行内公式增加概率）
                if random.random() < 0.5:  # 50%概率（提高以增加噪声）
                    result.append(random.choice(zw_chars))
                    # 有时插入多个零宽字符
                    if random.random() < 0.3:
                        result.append(random.choice(zw_chars))
            # 检测引号（属性值）
            elif char in ['"', "'"] and in_tag:
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                    result.append(char)
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                    result.append(char)
                    # 在属性值结束后随机插入零宽字符（增加概率）
                    if random.random() < 0.4:  # 40%概率（提高以增加噪声）
                        result.append(random.choice(zw_chars))
                        # 有时插入多个零宽字符
                        if random.random() < 0.3:
                            result.append(random.choice(zw_chars))
                else:
                    result.append(char)
            else:
                result.append(char)
                # 在标签内的属性名和值之间随机插入零宽字符（增加概率）
                # 但避免在 src=、href=、alt= 等关键属性后立即插入
                if in_tag and not in_quotes:
                    # 检查是否是关键属性（src, href, alt等）的等号后
                    # 如果最近几个字符包含 "src="、"href=" 等，不要插入零宽字符
                    recent_str = ''.join(recent_chars)
                    is_key_attr = any(key_attr in recent_str.lower() for key_attr in ['src=', 'href=', 'alt=', 'title=', 'data:'])
                    
                    if not is_key_attr and char in ['=', ' '] and random.random() < 0.3:  # 30%概率（提高）
                        result.append(random.choice(zw_chars))
                        # 有时插入多个零宽字符
                        if random.random() < 0.2:
                            result.append(random.choice(zw_chars))
            
            i += 1
        
        return ''.join(result)
    
    @staticmethod
    def _add_noise_to_image(base64_data_url: str, noise_intensity: float = 0.5) -> str:
        """
        为图片添加微小噪声，增加数据量以避免被微信公众号移除
        
        Args:
            base64_data_url: base64 编码的图片数据 URL
            noise_intensity: 噪声强度（0-1），值越小噪声越不明显
        
        Returns:
            添加噪声后的 base64 编码图片数据 URL
        """
        try:
            from PIL import Image
            import numpy as np
            from io import BytesIO
            
            # 解析 base64 数据 URL
            if ',' in base64_data_url:
                header, data = base64_data_url.split(',', 1)
                mime_type = header.split(';')[0].split(':')[1]
            else:
                data = base64_data_url
                mime_type = 'image/png'
            
            # 解码 base64
            image_data = base64.b64decode(data)
            
            # 使用 PIL 打开图片
            img = Image.open(BytesIO(image_data))
            
            # 转换为 RGBA 模式（如果还不是）
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 转换为 numpy 数组
            img_array = np.array(img, dtype=np.float32)
            
            # 添加较大的高斯噪声（只对非透明像素添加）
            # 使用更大的噪声强度，增加数据量以避免被微信公众号过滤
            # 噪声强度根据参数调整，范围通常在 0.8-1.2 之间
            noise_std = noise_intensity * 2.0  # 放大噪声标准差
            noise = np.random.normal(0, noise_std, img_array.shape).astype(np.float32)
            
            # 只对非透明像素添加噪声（alpha > 0）
            alpha_mask = img_array[:, :, 3:4] > 0
            # 对RGB通道添加噪声，保持alpha通道不变
            img_array[:, :, :3] = np.where(alpha_mask, 
                                           np.clip(img_array[:, :, :3] + noise[:, :, :3], 0, 255), 
                                           img_array[:, :, :3])
            
            # 额外添加一些随机像素点（增加数据量）
            # 对于行内公式，增加随机像素点的比例
            if noise_intensity > 0.5:
                # 在非透明区域随机添加随机像素（行内公式使用更高的比例）
                pixel_ratio = 0.005 if noise_intensity > 0.7 else 0.002  # 行内公式0.5%，块级公式0.2%
                random_mask = np.random.random(img_array.shape[:2]) < pixel_ratio
                random_mask = random_mask & (img_array[:, :, 3] > 0)  # 只在非透明区域
                if np.any(random_mask):
                    random_colors = np.random.randint(0, 256, size=(*img_array.shape[:2], 3), dtype=np.uint8)
                    img_array[:, :, :3] = np.where(
                        np.stack([random_mask] * 3, axis=2),
                        random_colors,
                        img_array[:, :, :3]
                    )
            
            # 对于行内公式，额外添加一些边缘像素噪声
            if noise_intensity > 0.7:
                # 在图片边缘添加一些噪声像素
                h, w = img_array.shape[:2]
                edge_mask = np.zeros((h, w), dtype=bool)
                edge_mask[0:2, :] = True  # 顶部边缘
                edge_mask[-2:, :] = True  # 底部边缘
                edge_mask[:, 0:2] = True  # 左侧边缘
                edge_mask[:, -2:] = True  # 右侧边缘
                edge_mask = edge_mask & (img_array[:, :, 3] > 0)
                if np.any(edge_mask):
                    edge_noise = np.random.normal(0, noise_std * 0.5, img_array.shape).astype(np.float32)
                    img_array[:, :, :3] = np.where(
                        np.stack([edge_mask] * 3, axis=2),
                        np.clip(img_array[:, :, :3] + edge_noise[:, :, :3], 0, 255),
                        img_array[:, :, :3]
                    )
            
            # 转换回 uint8
            img_array = np.clip(img_array, 0, 255).astype(np.uint8)
            
            # 转换回 PIL Image
            img_noisy = Image.fromarray(img_array, 'RGBA')
            
            # 保存到内存缓冲区
            buf = BytesIO()
            img_noisy.save(buf, format='PNG', optimize=False)  # 不优化以保持数据量
            
            # 转换为 base64
            buf.seek(0)
            image_data_noisy = buf.read()
            base64_data = base64.b64encode(image_data_noisy).decode('utf-8')
            
            return f"data:{mime_type};base64,{base64_data}"
        except Exception as e:
            # 如果添加噪声失败，返回原始图片
            print(f"Warning: Failed to add noise to image: {e}")
            return base64_data_url
    
    def render_latex_to_base64(self, latex: str, is_inline: bool = False) -> str:
        """
        将 LaTeX 公式渲染为图片并转换为 base64
        
        Args:
            latex: LaTeX 公式代码
            is_inline: 是否为行内公式（True）或块级公式（False）
        
        Returns:
            base64 编码的图片数据 URL
        """
        # 优先使用 CodeCogs 渲染（下载图片并转为 base64）
        # CodeCogs 支持更复杂的 LaTeX 公式，渲染质量更好
        try:
            result = self._render_with_codecogs(latex, is_inline)
        except Exception as e:
            print(f"Warning: Failed to render formula with CodeCogs: {e}")
            # 备选方案：尝试使用 sympy + matplotlib
            try:
                result = self._render_with_sympy_matplotlib(latex, is_inline)
            except ImportError:
                # 如果没有 sympy，尝试使用 matplotlib
                try:
                    result = self._render_with_matplotlib(latex, is_inline)
                except ImportError:
                    print("Warning: matplotlib not available, formula rendering failed")
                    # 返回占位符
                    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            except Exception as e2:
                print(f"Warning: Failed to render formula with sympy/matplotlib: {e2}")
                # 返回占位符
                return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        return result
    
    def _render_with_sympy_matplotlib(self, latex: str, is_inline: bool = False) -> str:
        """使用 sympy + matplotlib 渲染 LaTeX 公式（更好的复杂公式支持）"""
        import matplotlib
        matplotlib.use('Agg')  # 使用非交互式后端
        import matplotlib.pyplot as plt
        from io import BytesIO
        from sympy import sympify, latex as sympy_latex, SympifyError
        
        # 忽略警告
        import warnings
        import logging
        warnings.filterwarnings('ignore', category=UserWarning)
        logging.getLogger('matplotlib').setLevel(logging.ERROR)
        logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
        
        # 尝试使用 sympy 优化 LaTeX（如果可能）
        # 先清理 LaTeX 中的 $ 符号（可能来自公式解析时的残留）
        cleaned_latex = latex.strip().strip('$')
        try:
            # 尝试将 LaTeX 解析为 sympy 表达式再转回 LaTeX（优化格式）
            # 注意：这只能处理简单的表达式，复杂公式保持原样
            # sympy 不支持包含 $ 符号的 LaTeX，所以使用清理后的版本
            expr = sympify(cleaned_latex, evaluate=False)
            optimized_latex = sympy_latex(expr)
            # 如果优化后的 LaTeX 太短或与原式差异太大，使用原式
            if len(optimized_latex) < len(cleaned_latex) * 0.5:
                optimized_latex = cleaned_latex
        except (SympifyError, Exception):
            # 如果无法解析，直接使用清理后的 LaTeX（不包含 $ 符号）
            optimized_latex = cleaned_latex
        
        # 设置字体
        plt.rcParams['mathtext.fontset'] = 'dejavusans'
        plt.rcParams['font.family'] = 'sans-serif'
        
        # 使用浅黄色背景（#FFF8DC），避免图片太小或内容太少被腾讯公众号清洗掉
        formula_bg_color = '#FFF8DC'  # 浅黄色背景
        
        # 根据公式复杂度动态调整图片尺寸
        # 检测公式是否包含矩阵、多个等号等复杂结构
        has_matrix = 'bmatrix' in optimized_latex or 'pmatrix' in optimized_latex or 'vmatrix' in optimized_latex
        has_multiple_equals = optimized_latex.count('=') > 1
        is_long_formula = len(optimized_latex) > 100
        
        # 创建图形（行内公式使用更小的尺寸）
        if is_inline:
            # 行内公式：使用非常小的图形，只包含公式内容
            fig, ax = plt.subplots(figsize=(6, 0.4), facecolor=formula_bg_color)
        else:
            # 块级公式：根据复杂度调整尺寸
            if has_matrix or has_multiple_equals or is_long_formula:
                # 复杂公式（包含矩阵、多个等号或较长）：使用更大的图形
                fig, ax = plt.subplots(figsize=(16, 2.0), facecolor=formula_bg_color)
            else:
                # 普通块级公式：使用标准尺寸
                fig, ax = plt.subplots(figsize=(10, 1.5), facecolor=formula_bg_color)
        
        ax.axis('off')
        ax.set_facecolor(formula_bg_color)
        
        # 渲染公式
        fontsize = 12 if is_inline else 18
        
        # 处理 LaTeX 代码
        # optimized_latex 已经清理过 $ 符号，直接使用
        if is_inline:
            formula_text = f'${optimized_latex}$'
        else:
            # 块级公式不需要 $ 符号
            formula_text = optimized_latex
        
        ax.text(0.5, 0.5, formula_text,
                fontsize=fontsize, ha='center', va='center',
                transform=ax.transAxes, usetex=False)
        
        # 保存到内存缓冲区（使用浅黄色背景）
        # 对于复杂公式，使用更高的 DPI 以确保清晰度
        dpi = 150 if is_inline else (250 if (has_matrix or has_multiple_equals or is_long_formula) else 200)
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=dpi, 
                   bbox_inches='tight', pad_inches=0.05 if is_inline else 0.1,
                   facecolor=formula_bg_color, transparent=False)
        plt.close(fig)
        
        # 转换为 base64
        buf.seek(0)
        image_data = buf.read()
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        # 获取 MIME 类型
        mime_type = 'image/png'
        return f"data:{mime_type};base64,{base64_data}"
    
    def _render_with_matplotlib(self, latex: str, is_inline: bool = False) -> str:
        """使用 matplotlib 渲染 LaTeX 公式"""
        import matplotlib
        matplotlib.use('Agg')  # 使用非交互式后端
        import matplotlib.pyplot as plt
        from io import BytesIO
        
        # 设置字体（使用数学字体）
        # 使用 dejavusans 字体，支持更多字符，避免全角字符警告
        plt.rcParams['mathtext.fontset'] = 'dejavusans'  # 支持更多字符
        plt.rcParams['font.family'] = 'sans-serif'
        # 忽略字体警告（如果某些字符无法找到，matplotlib 会自动使用备用字符）
        import warnings
        import logging
        # 过滤所有 matplotlib 相关的警告
        warnings.filterwarnings('ignore', category=UserWarning)
        # 设置 matplotlib 日志级别，避免字体警告输出到控制台
        logging.getLogger('matplotlib').setLevel(logging.ERROR)
        logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
        
        # 使用浅黄色背景（#FFF8DC），避免图片太小或内容太少被腾讯公众号清洗掉
        formula_bg_color = '#FFF8DC'  # 浅黄色背景
        
        # 处理 LaTeX 代码：确保块级公式不包含 $ 符号
        # 先清理 LaTeX 中的 $ 符号（可能来自公式解析时的残留）
        cleaned_latex = latex.strip().strip('$')
        
        # 根据公式复杂度动态调整图片尺寸
        # 检测公式是否包含矩阵、多个等号等复杂结构
        has_matrix = 'bmatrix' in cleaned_latex or 'pmatrix' in cleaned_latex or 'vmatrix' in cleaned_latex
        has_multiple_equals = cleaned_latex.count('=') > 1
        is_long_formula = len(cleaned_latex) > 100
        
        # 创建图形（行内公式使用更小的尺寸）
        if is_inline:
            # 行内公式：使用非常小的图形，只包含公式内容
            fig, ax = plt.subplots(figsize=(6, 0.4), facecolor=formula_bg_color)
        else:
            # 块级公式：根据复杂度调整尺寸
            if has_matrix or has_multiple_equals or is_long_formula:
                # 复杂公式（包含矩阵、多个等号或较长）：使用更大的图形
                fig, ax = plt.subplots(figsize=(16, 2.0), facecolor=formula_bg_color)
            else:
                # 普通块级公式：使用标准尺寸
                fig, ax = plt.subplots(figsize=(10, 1.5), facecolor=formula_bg_color)
        
        ax.axis('off')
        ax.set_facecolor(formula_bg_color)
        
        # 渲染公式（行内公式使用更小的字体）
        fontsize = 12 if is_inline else 18
        
        if is_inline:
            formula_text = f'${cleaned_latex}$'
        else:
            # 块级公式不需要 $ 符号
            formula_text = cleaned_latex
        
        ax.text(0.5, 0.5, formula_text,
                fontsize=fontsize, ha='center', va='center',
                transform=ax.transAxes, usetex=False)  # 使用 matplotlib 的数学文本渲染
        
        # 保存到内存缓冲区（使用浅黄色背景）
        # 对于复杂公式，使用更高的 DPI 以确保清晰度
        dpi = 150 if is_inline else (250 if (has_matrix or has_multiple_equals or is_long_formula) else 200)
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=dpi, 
                   bbox_inches='tight', pad_inches=0.05 if is_inline else 0.1,
                   facecolor=formula_bg_color, transparent=False)
        plt.close(fig)
        
        # 转换为 base64
        buf.seek(0)
        image_data = buf.read()
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        # 如果启用了临时文件记录（用于调试），可以保存到文件
        if not self.cleanup and self.temp_dir:
            import uuid
            temp_file = self.temp_dir / f"formula_{uuid.uuid4().hex}.png"
            with open(temp_file, 'wb') as f:
                f.write(image_data)
            self.temp_files.append(temp_file)
        
        # 获取 MIME 类型
        mime_type = 'image/png'
        return f"data:{mime_type};base64,{base64_data}"
    
    def _render_with_codecogs(self, latex: str, is_inline: bool = False) -> str:
        """
        使用 CodeCogs 在线服务渲染公式，下载图片并转为 base64
        
        Args:
            latex: LaTeX 公式代码
            is_inline: 是否为行内公式（True）或块级公式（False）
        
        Returns:
            base64 编码的图片数据 URL
        """
        from urllib.parse import quote
        import urllib.request
        import re
        
        # 先清理 LaTeX 中的 $ 符号（可能来自公式解析时的残留）
        latex = latex.strip().strip('$')
        
        # 转换 cases 环境为 array 环境（CodeCogs 不支持 cases）
        # \begin{cases}...\end{cases} -> \left\{\begin{array}{ll}...\end{array}\right.
        latex = self._convert_cases_to_array(latex)
        
        # 根据公式复杂度动态调整 DPI
        # 检测公式是否包含矩阵、多个等号等复杂结构
        has_matrix = 'bmatrix' in latex or 'pmatrix' in latex or 'vmatrix' in latex
        has_multiple_equals = latex.count('=') > 1
        is_long_formula = len(latex) > 100
        
        # 设置 DPI（行内公式使用较小 DPI，块级公式根据复杂度调整）
        if is_inline:
            dpi = 120
        elif has_matrix or has_multiple_equals or is_long_formula:
            # 复杂公式使用更高的 DPI
            dpi = 200
        else:
            dpi = 150
        
        # CodeCogs 渲染的图片会添加浅黄色背景（#FFF8DC），保持与 matplotlib/sympy 渲染的一致性
        # 构建 CodeCogs URL（下载后会添加浅黄色背景）
        query_part = f"\\dpi{{{dpi}}} {latex}"
        encoded_query = quote(query_part, safe='')
        url = f"https://latex.codecogs.com/png.image?{encoded_query}"
        
        try:
            # 从 CodeCogs 下载渲染好的图片
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'Mozilla/5.0 (compatible; MD2WeChat/1.0)')
            response = urllib.request.urlopen(request, timeout=15)
            image_data = response.read()
            
            # 验证是否为有效的图片数据
            if len(image_data) < 100:  # 太小的数据可能是错误页面
                raise ValueError("Invalid image data from CodeCogs")
            
            # 为 CodeCogs 渲染的图片添加浅黄色背景，保持与 matplotlib/sympy 渲染的一致性
            try:
                from PIL import Image
                from io import BytesIO
                
                # 打开图片
                img = Image.open(BytesIO(image_data))
                
                # 如果图片有透明通道，需要添加背景色
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    # 创建浅黄色背景（#FFF8DC）
                    bg_color = (255, 248, 220)  # RGB 值对应 #FFF8DC
                    
                    # 转换为 RGBA 模式以便处理透明度
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    # 创建背景图片
                    bg = Image.new('RGB', img.size, bg_color)
                    
                    # 将原图片合成到背景上
                    bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                    img = bg
                elif img.mode != 'RGB':
                    # 如果不是 RGB 模式，转换为 RGB
                    img = img.convert('RGB')
                
                # 保存到内存缓冲区
                output = BytesIO()
                img.save(output, format='PNG')
                image_data = output.getvalue()
            except Exception as e:
                # 如果 PIL 处理失败，使用原始图片数据
                print(f"Warning: Failed to add background color to CodeCogs image: {e}")
            
            # 转换为 base64
            base64_data = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/png;base64,{base64_data}"
        except urllib.error.HTTPError as e:
            print(f"Warning: HTTP error when fetching formula from CodeCogs: {e.code} - {e.reason}")
            raise
        except urllib.error.URLError as e:
            print(f"Warning: URL error when fetching formula from CodeCogs: {e.reason}")
            raise
        except Exception as e:
            print(f"Warning: Failed to fetch formula from CodeCogs: {e}")
            raise
    
    @staticmethod
    def latex_to_url(latex: str, is_inline: bool = False) -> str:
        """
        将 LaTeX 代码转换为 CodeCogs 图片 URL（已废弃，保留用于兼容性）
        
        Args:
            latex: LaTeX 公式代码
            is_inline: 是否为行内公式（True）或块级公式（False）
        
        Returns:
            CodeCogs 图片 URL
        """
        from urllib.parse import quote
        
        # 构建 CodeCogs URL
        # 对于块级公式，使用更大的 dpi
        dpi = 150 if not is_inline else 120
        
        # CodeCogs URL 格式：整个查询参数需要进行 URL 编码
        # 包括 \dpi{150} 和 LaTeX 公式部分（使用透明背景）
        # 格式：https://latex.codecogs.com/png.image?{fully_encoded_query}
        
        # 构建查询参数字符串（透明背景，移除 \bg_white）
        query_part = f"\\dpi{{{dpi}}} {latex}"
        
        # 对整个查询参数进行 URL 编码
        # 反斜杠编码为 %5C，空格编码为 %20，大括号编码为 %7B 和 %7D
        encoded_query = quote(query_part, safe='')
        
        # 构建完整 URL
        url = f"https://latex.codecogs.com/png.image?{encoded_query}"
        
        return url
    
    def format_inline_formula(self, latex: str) -> str:
        """
        格式化行内公式
        
        Args:
            latex: LaTeX 公式代码
        
        Returns:
            HTML span 标签（内联显示，base64 嵌入，带米黄色背景）
        """
        data_url = self.render_latex_to_base64(latex, is_inline=True)
        # 行内公式样式：使用 span 包裹，添加米黄色背景
        html = f'<span style="display:inline-block;vertical-align:middle;background-color:#FFF8DC;padding:2px 4px;border-radius:3px;"><img src="{data_url}" style="display:inline-block;vertical-align:middle;max-height:1.2em;height:auto;width:auto;"></span>'
        return html
    
    def format_block_formula(self, latex: str) -> str:
        """
        格式化块级公式（居中显示，带浅色背景强调）
        
        Args:
            latex: LaTeX 公式代码
        
        Returns:
            HTML 段落标签（居中显示，base64 嵌入，带米黄色背景）
        """
        data_url = self.render_latex_to_base64(latex, is_inline=False)
        # 块级公式使用米黄色背景（#FFF8DC）来强调，添加内边距和圆角
        html = f'''<div style="text-align:center;background-color:#FFF8DC;padding:10px;border-radius:6px;margin:10px 0;">
  <img src="{data_url}" style="width:auto;max-width:90%;">
</div><br>'''
        return html
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        if self.cleanup:
            for temp_file in self.temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete temp file {temp_file}: {e}")


class MermaidProcessor:
    """Mermaid 图处理器 - 使用 mmdc 转换为 PNG 并转为 base64"""
    
    def __init__(self, temp_dir: Optional[str] = None, cleanup: bool = True, style_config: Optional[StyleConfig] = None):
        """
        Args:
            temp_dir: 临时文件目录（默认：系统临时目录）
            cleanup: 是否在转换完成后清理临时文件
            style_config: 样式配置（用于适配主题背景色）
        """
        import tempfile
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "md2wechat_mermaid"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup = cleanup
        self.temp_files = []  # 记录临时文件，用于清理
        self.style_config = style_config
    
    @staticmethod
    def _is_light_color(color: str) -> bool:
        """
        判断颜色是否为亮色
        
        Args:
            color: 颜色字符串（支持 #RRGGBB, rgb(r,g,b), rgba(r,g,b,a) 格式）
        
        Returns:
            True 如果为亮色，False 如果为暗色
        """
        import re
        
        # 解析颜色值
        r, g, b = 255, 255, 255  # 默认白色
        
        # 处理 #RRGGBB 格式
        hex_match = re.match(r'^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$', color)
        if hex_match:
            r = int(hex_match.group(1), 16)
            g = int(hex_match.group(2), 16)
            b = int(hex_match.group(3), 16)
        else:
            # 处理 rgba(r, g, b, a) 或 rgb(r, g, b) 格式
            rgba_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)', color)
            if rgba_match:
                r = int(rgba_match.group(1))
                g = int(rgba_match.group(2))
                b = int(rgba_match.group(3))
        
        # 计算亮度（使用相对亮度公式）
        # Y = 0.299*R + 0.587*G + 0.114*B
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        
        # 如果亮度大于 128，认为是亮色
        return brightness > 128
    
    def convert_mermaid_to_png_base64(self, mermaid_code: str) -> str:
        """
        将 Mermaid 代码转换为 PNG 并转为 base64
        
        Args:
            mermaid_code: Mermaid 代码
        
        Returns:
            base64 编码的 PNG 数据 URL
        """
        import subprocess
        import uuid
        
        # 生成临时文件路径
        temp_id = uuid.uuid4().hex
        mermaid_file = self.temp_dir / f"mermaid_{temp_id}.mmd"
        png_file = self.temp_dir / f"mermaid_{temp_id}.png"
        
        try:
            # 写入 Mermaid 代码到临时文件
            with open(mermaid_file, 'w', encoding='utf-8') as f:
                f.write(mermaid_code)
            
            # 始终使用透明背景，在 HTML 层面添加浅色绿色背景容器来强调
            
            # 检查是否需要设置宽高比（检测 graph LR 横向布局，通常需要更宽的图片）
            # 如果包含 "graph LR" 且包含 style 配置，可能是需要特定宽高比的总结图
            mmdc_args = ['mmdc', '-i', str(mermaid_file), '-o', str(png_file), '-b', 'transparent']
            
            # 检测是否为横向布局的总结图（通常需要 2.35:1 宽高比）
            if 'graph LR' in mermaid_code and 'style' in mermaid_code:
                # 设置宽高比为 2.35:1，例如宽度 2350px，高度 1000px
                mmdc_args.extend(['-w', '2350', '-H', '1000'])
            
            # 使用 mmdc 转换为 PNG
            result = subprocess.run(
                mmdc_args,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"mmdc failed: {result.stderr}")
            
            if not png_file.exists():
                raise FileNotFoundError(f"PNG file not created: {png_file}")
            
            # 读取 PNG 文件
            with open(png_file, 'rb') as f:
                png_data = f.read()
            
            # 转换为 base64
            base64_data = base64.b64encode(png_data).decode('utf-8')
            
            # 记录临时文件
            if self.cleanup:
                self.temp_files.extend([mermaid_file, png_file])
            
            return f"data:image/png;base64,{base64_data}"
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("Mermaid conversion timed out")
        except FileNotFoundError:
            raise RuntimeError("mmdc command not found. Please install @mermaid-js/mermaid-cli")
        except Exception as e:
            raise RuntimeError(f"Failed to convert Mermaid: {e}")
    
    def format_mermaid(self, mermaid_code: str) -> str:
        """
        格式化 Mermaid 图为 HTML div 标签（带极浅绿色背景强调）
        
        Args:
            mermaid_code: Mermaid 代码
        
        Returns:
            HTML div 标签（居中显示，base64 嵌入 PNG，带极浅绿色背景）
        """
        try:
            data_url = self.convert_mermaid_to_png_base64(mermaid_code)
            # 使用极浅绿色背景（#F0FFF0）来强调 Mermaid 图表，添加内边距和圆角
            return f'''<div style="display:block;text-align:center;background-color:#F0FFF0;padding:12px;border-radius:8px;margin:10px 0;">
    <img src="{data_url}" style="max-width:100%;height:auto;">
</div><br>'''
        except Exception as e:
            print(f"Warning: Failed to render Mermaid diagram: {e}")
            # 返回错误提示（也带极浅绿色背景）
            return f'''<div style="display:block;text-align:center;color:#FF0000;background-color:#F0FFF0;padding:12px;border-radius:8px;margin:10px 0;">
    Mermaid 图表渲染失败: {str(e)}
</div><br>'''
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        if self.cleanup:
            for temp_file in self.temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete temp file {temp_file}: {e}")


class ImageProcessor:
    """图片处理器 - 支持 base64 嵌入"""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Args:
            base_dir: Markdown 文件所在目录，用于解析相对路径
        """
        self.base_dir = Path(base_dir) if base_dir else None
    
    def process_image(self, src: str, alt: str = "", title: str = "", image_number: int = 0) -> str:
        """
        处理图片，转换为 base64 嵌入格式，并显示图名和编号
        
        Args:
            src: 图片路径（本地或URL）
            alt: 图片替代文本（将作为图名显示）
            title: 图片标题（未使用，保留用于兼容性）
            image_number: 图片编号（从1开始）
        
        Returns:
            HTML img 标签（base64 格式），包含图名和编号
        """
        # 尝试解析为 base64
        base64_data = self._get_image_base64(src)
        
        # 构建图名（如果有 alt 文本，则使用 alt，否则使用空字符串）
        image_name = alt.strip() if alt else ""
        
        # 构建图名显示部分
        if image_number > 0:
            # 正文图片：显示完整的"图 x. 标题"格式
            if image_name:
                caption_text = f"图{image_number}：{image_name}"
            else:
                caption_text = f"图{image_number}"
        else:
            # 卷首图片：完全不显示编号和图名
            caption_text = ""
        
        # 转义图名中的 HTML 特殊字符
        escaped_caption = self._escape_html(caption_text) if caption_text else ""
        
        # 构建图片 HTML
        if base64_data:
            # 获取 MIME 类型
            mime_type = self._get_mime_type(src)
            data_url = f"data:{mime_type};base64,{base64_data}"
            
            img_html = f"""<span style="display:block;text-align:center;">
    <img src="{data_url}" alt="{self._escape_html(alt)}" style="max-width:100%;height:auto;border:1px solid #EAEAEA;">"""
        else:
            # 如果无法转换为 base64，使用原始 URL
            img_html = f"""<span style="display:block;text-align:center;">
    <img src="{src}" alt="{self._escape_html(alt)}" style="max-width:100%;height:auto;border:1px solid #EAEAEA;">"""
        
        # 如果有图名，添加图名显示（小字体、淡颜色）
        if escaped_caption:
            img_html += f"""
    <div style="font-size:0.85em;color:#888888;margin-top:6px;line-height:1.4;">{escaped_caption}</div>"""
        
        img_html += """
</span><br>"""
        
        return img_html
    
    def _get_image_base64(self, src: str) -> Optional[str]:
        """获取图片的 base64 编码"""
        try:
            # 判断是 URL 还是本地路径
            parsed = urlparse(src)
            
            if parsed.scheme in ('http', 'https'):
                # 网络图片
                response = requests.get(src, timeout=10)
                if response.status_code == 200:
                    return base64.b64encode(response.content).decode('utf-8')
            else:
                # 本地图片
                if self.base_dir:
                    img_path = self.base_dir / src
                else:
                    img_path = Path(src)
                
                if img_path.exists() and img_path.is_file():
                    with open(img_path, 'rb') as f:
                        return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"Warning: 无法处理图片 {src}: {e}")
        
        return None
    
    def _get_mime_type(self, src: str) -> str:
        """获取图片 MIME 类型"""
        mime_type, _ = mimetypes.guess_type(src)
        if not mime_type:
            # 根据扩展名推断
            ext = Path(src).suffix.lower()
            mime_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
            }
            mime_type = mime_map.get(ext, 'image/png')
        return mime_type
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        return (text.replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;")
                  .replace('"', "&quot;")
                  .replace("'", "&#39;"))


class WeChatHTMLConverter:
    """Markdown 转微信公众号 HTML 转换器"""
    
    def __init__(self, style: str = "academic_gray", base_dir: Optional[str] = None):
        """
        Args:
            style: 风格名称（默认 "academic_gray"）
            base_dir: Markdown 文件所在目录，用于解析图片路径
        """
        if style not in STYLES:
            raise ValueError(f"未知的风格: {style}. 可用风格: {list(STYLES.keys())}")
        
        self.style_config = STYLES[style]
        self.image_processor = ImageProcessor(base_dir)
        self.code_formatter = CodeBlockFormatter(style_config=self.style_config)
        # FormulaProcessor 需要实例化，以便管理临时文件，传入样式配置以适配主题
        self.formula_processor = FormulaProcessor(style_config=self.style_config)
        # MermaidProcessor 需要实例化，以便管理临时文件，传入样式配置以适配主题
        self.mermaid_processor = MermaidProcessor(style_config=self.style_config)
        # 图片计数器，用于为图片编号
        self.image_counter = 0
    
    def convert(self, md_file: str, source: Optional[str] = None) -> str:
        """
        转换 Markdown 文件为微信公众号 HTML
        
        Args:
            md_file: Markdown 文件路径
            source: 来源信息（可选，如果提供则覆盖 Front Matter 中的来源）
        
        Returns:
            转换后的 HTML 字符串
        """
        # 读取 Markdown 文件
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # 解析 Markdown
        parser = MarkdownParser(md_content)
        
        # 提取元信息
        title = parser.get_front_matter("title", "")
        date = parser.get_front_matter("date", "")
        tags = parser.get_front_matter("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        permalink = parser.get_front_matter("permalink", "")
        
        # 提取来源信息
        # 优先级：参数 source > Front Matter tags 中的来源 > 默认值
        extracted_source = None
        
        # 如果参数提供了 source，直接使用
        if source:
            extracted_source = source
        else:
            # 从 tags 中查找来源信息
            # 支持格式：来源:xxx、source:xxx、来源：xxx、source：xxx
            for tag in tags:
                if isinstance(tag, str):
                    # 检查是否是来源标签
                    if tag.startswith("来源:") or tag.startswith("来源："):
                        extracted_source = tag.split(":", 1)[-1].split("：", 1)[-1].strip()
                        break
                    elif tag.startswith("source:") or tag.startswith("source："):
                        extracted_source = tag.split(":", 1)[-1].split("：", 1)[-1].strip()
                        break
        
        # 如果都没有，使用默认值
        if not extracted_source:
            extracted_source = "gnss.ac.cn"
        
        # 重置图片计数器
        self.image_counter = 0
        
        # 转换 body
        html_body = self._convert_body(parser.body)
        
        # 生成完整 HTML
        return self._generate_html(title, date, tags, html_body, extracted_source, permalink)
    
    def _convert_body(self, md_body: str) -> str:
        """将 Markdown 正文转换为 HTML（按章节 H3 分块，忽略 H1，H2 使用粗横线格式）"""
        import re
        
        # 正则表达式：ATX 标题（忽略前导空格、尾部 #）
        _ATX_H_RE = re.compile(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$')
        # 图片正则：支持带 title 和不带 title 两种格式
        _IMG_RE_1 = re.compile(r'!\[([^\]]*)\]\((\S+?)\s+"([^"]+)"\)')
        _IMG_RE_2 = re.compile(r'!\[([^\]]*)\]\((\S+?)\)')
        
        def _strip_front_matter(lines):
            """去掉 --- 包裹的 YAML front-matter"""
            if len(lines) >= 3 and lines[0].strip() == '---':
                i = 1
                while i < len(lines) and lines[i].strip() != '---':
                    i += 1
                if i < len(lines) and lines[i].strip() == '---':
                    return lines[i+1:]
            return lines
        
        lines = md_body.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        lines = _strip_front_matter(lines)
        
        sections = []  # [{level:int, title:str, items:list[tuple]}]
        cur = None
        
        in_code = False
        code_lang = ""
        buf_code = []
        
        in_formula = False  # $$ block
        buf_formula = []
        
        def flush_para_buffer(parabuf):
            if not parabuf:
                return
            # 合并连续段落为一个 item，保留空行信息
            text = '\n'.join(parabuf)
            (cur['items'] if cur else preface).append(('paragraph', text))
            parabuf.clear()
        
        preface = []   # 卷首语（tag头后的内容，直到第一个 H3）
        parabuf = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 代码围栏 ```lang
            if line.lstrip().startswith('```'):
                fence = line.strip()
                if not in_code:
                    in_code = True
                    code_lang = fence[3:].strip()
                    buf_code = []
                else:
                    # 结束代码块
                    flush_para_buffer(parabuf)
                    (cur['items'] if cur else preface).append(
                        ('mermaid', '\n'.join(buf_code)) if code_lang.lower()=='mermaid'
                        else ('code', '\n'.join(buf_code), code_lang)
                    )
                    in_code = False
                    code_lang = ""
                    buf_code = []
                i += 1
                continue
            if in_code:
                buf_code.append(line)
                i += 1
                continue
            
            # 公式块 $$（需要在列表项之前检查，以便在列表项中也能识别）
            # 检查整行是否是公式块（单行 $$...$$ 或多行开始/结束）
            stripped_line = line.strip()
            if stripped_line.startswith('$$'):
                if not in_formula:
                    in_formula = True
                    content = stripped_line[2:]
                    if content.endswith('$$'):
                        # 单行 $$...$$
                        content = content[:-2]
                        flush_para_buffer(parabuf)
                        # 清理公式内容中的所有 $ 符号（防止残留）
                        formula_content = content.strip().strip('$')
                        (cur['items'] if cur else preface).append(('formula', formula_content))
                        in_formula = False
                    else:
                        buf_formula = [content]
                else:
                    # 结束
                    content = '\n'.join(buf_formula)
                    tail = stripped_line
                    if tail != '$$':
                        # 容错：末行可能还有内容
                        # 移除末尾的 $$，但保留其他内容
                        tail_cleaned = tail.rstrip('$').rstrip('$') if tail.endswith('$$') else tail.replace('$$', '')
                        content += '\n' + tail_cleaned
                    flush_para_buffer(parabuf)
                    # 清理公式内容中的所有 $ 符号（防止残留）
                    formula_content = content.strip()
                    # 移除首尾的 $ 符号
                    formula_content = formula_content.strip('$')
                    # 移除内容中可能残留的 $$（虽然不应该有，但容错处理）
                    formula_content = formula_content.replace('$$', '').replace('$$', '')
                    (cur['items'] if cur else preface).append(('formula', formula_content))
                    in_formula = False
                    buf_formula = []
                i += 1
                continue
            if in_formula:
                buf_formula.append(line)
                i += 1
                continue
            
            # 检查段落中是否包含单行块级公式 $$...$$（不在行首的情况）
            # 这需要在段落处理之前检查，以便正确提取公式
            # 使用更精确的正则表达式，匹配 $$...$$ 但不匹配 $$$...$$$ 或更多 $
            para_formula_match = re.search(r'(?<!\$)\$\$((?:[^$]|\$(?!\$))+)\$\$(?!\$)', line)
            if para_formula_match and not in_code and not in_formula:
                # 在段落中找到公式，需要分割段落
                formula_content = para_formula_match.group(1).strip()
                before_formula = line[:para_formula_match.start()].rstrip()
                after_formula = line[para_formula_match.end():].lstrip()
                
                # 如果公式前有内容，先添加为段落
                if before_formula.strip():
                    parabuf.append(before_formula)
                    flush_para_buffer(parabuf)
                
                # 添加公式
                flush_para_buffer(parabuf)
                (cur['items'] if cur else preface).append(('formula', formula_content))
                
                # 如果公式后有内容，继续处理
                if after_formula.strip():
                    parabuf.append(after_formula)
                
                i += 1
                continue
            
            # 图片（整行图片）
            m = _IMG_RE_1.search(line)
            if m and line.strip().startswith('!['):
                alt = m.group(1) or ""
                src = m.group(2)
                title = m.group(3)
            else:
                m = _IMG_RE_2.search(line)
                if m and line.strip().startswith('!['):
                    alt = m.group(1) or ""
                    src = m.group(2)
                    title = ""
                else:
                    m = None
            
            if m:
                flush_para_buffer(parabuf)
                (cur['items'] if cur else preface).append(('image', src, alt, title))
                i += 1
                continue
            
            # ATX 标题（H1..H6）
            hm = _ATX_H_RE.match(line)
            if hm:
                flush_para_buffer(parabuf)
                level = len(hm.group(1))
                text = hm.group(2).strip()
                
                if level == 1:
                    # H1 忽略，不作为分块依据，也不显示
                    i += 1
                    continue
                elif level == 2:
                    # H2 作为分块依据
                    if cur:
                        sections.append(cur)
                    else:
                        # 如果前面有卷首语，先输出卷首语作为独立章节
                        if preface:
                            sections.append({'level': 0, 'title': '', 'items': preface[:]})
                            preface = []
                    # H2 创建一个新的分块
                    cur = {'level': level, 'title': text, 'items': []}
                elif level == 3:
                    # H3 也作为分块依据（H3到下一个H2或H3之间的内容属于这个H3）
                    if cur:
                        sections.append(cur)
                    else:
                        # 如果前面有卷首语，先输出卷首语作为独立章节
                        if preface:
                            sections.append({'level': 0, 'title': '', 'items': preface[:]})
                            preface = []
                    # H3 创建一个新的分块
                    cur = {'level': level, 'title': text, 'items': []}
                else:
                    # H4+ 作为当前章节的普通项
                    (cur['items'] if cur else preface).append(('heading', text, level))
                i += 1
                continue
            
            # 列表项（无序列表：- * +，有序列表：数字.）
            list_match = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.+)$', line)
            if list_match:
                flush_para_buffer(parabuf)
                indent = len(list_match.group(1))
                marker = list_match.group(2)
                item_text = list_match.group(3)
                is_ordered = marker not in ['-', '*', '+']
                # 保持列表项完整，公式在渲染时处理
                (cur['items'] if cur else preface).append(('list_item', item_text, indent, is_ordered))
                i += 1
                continue
            
            # 表格行（包含 | 分隔符）
            if '|' in line and line.strip().startswith('|') and line.strip().endswith('|'):
                stripped_line = line.strip()
                # 检查是否是表格分隔行：每个单元格只包含 -、:、空格，且不包含字母数字
                cells = [cell.strip() for cell in stripped_line.split('|')[1:-1]]
                is_separator = True
                if not cells:
                    is_separator = False
                else:
                    for cell in cells:
                        # 单元格只包含 -、:、空格，且不包含字母数字，且至少包含一个 -
                        if not re.match(r'^[\s\-:]+$', cell) or re.search(r'[a-zA-Z0-9]', cell) or '-' not in cell:
                            is_separator = False
                            break
                
                if is_separator:
                    # 表格分隔行，解析对齐方式
                    alignments = []
                    for cell in cells:
                        cell = cell.strip()
                        if cell.startswith(':') and cell.endswith(':'):
                            alignments.append('center')
                        elif cell.endswith(':'):
                            alignments.append('right')
                        else:
                            alignments.append('left')
                    flush_para_buffer(parabuf)
                    (cur['items'] if cur else preface).append(('table_separator', alignments))
                    i += 1
                    continue
                else:
                    # 表格数据行
                    flush_para_buffer(parabuf)
                    (cur['items'] if cur else preface).append(('table_row', cells))
                    i += 1
                    continue
            
            # 引用块（以 > 开头的行）
            if line.lstrip().startswith('>'):
                flush_para_buffer(parabuf)
                # 收集连续的引用行
                quote_lines = []
                while i < len(lines) and lines[i].lstrip().startswith('>'):
                    # 移除前导的 > 和空格
                    quote_line = lines[i].lstrip()[1:].lstrip()
                    quote_lines.append(quote_line)
                    i += 1
                # 合并多行引用为一个段落
                quote_text = ' '.join(quote_lines)
                (cur['items'] if cur else preface).append(('blockquote', quote_text))
                continue
            
            # 水平分割线（---, ***, ___，至少3个，前后可以有空格）
            stripped = line.strip()
            if stripped and len(stripped) >= 3:
                # 检查是否全部是 -、* 或 _
                if stripped.replace('-', '').replace('*', '').replace('_', '') == '':
                    # 至少3个相同的字符
                    if (stripped.count('-') >= 3 and stripped.replace('-', '') == '') or \
                       (stripped.count('*') >= 3 and stripped.replace('*', '') == '') or \
                       (stripped.count('_') >= 3 and stripped.replace('_', '') == ''):
                        flush_para_buffer(parabuf)
                        (cur['items'] if cur else preface).append(('horizontal_rule',))
                        i += 1
                        continue
            
            # 空行
            if not line.strip():
                parabuf.append('')
                i += 1
                continue
            
            # 检查是否是列表项的延续行（列表项内容中的换行，不应该被识别为新列表项）
            # 这需要检查前一个 item 是否是列表项，且当前行不是新的列表项标记
            if (cur and cur['items'] or preface):
                # 检查最后一个 item 是否是列表项
                last_items = cur['items'] if cur else preface
                if last_items:
                    last_item = last_items[-1]
                    if isinstance(last_item, tuple) and len(last_item) > 0 and last_item[0] == 'list_item':
                        # 前一个是列表项，检查当前行是否是延续
                        line_stripped = line.lstrip()
                        line_indent = len(line) - len(line_stripped)
                        list_indent = last_item[2] if len(last_item) > 2 else 0
                        
                        # 检查是否是列表标记（新的列表项）
                        is_list_marker = bool(re.match(r'^([-*+]|\d+\.)\s+', line_stripped))
                        
                        # 检查是否是其他特殊格式（标题、代码块开始、图片等）
                        is_special_format = (
                            _ATX_H_RE.match(line) or  # 标题
                            line.lstrip().startswith('```') or  # 代码块
                            line.lstrip().startswith('$$') or  # 公式块
                            line.strip().startswith('![') or  # 图片
                            ('|' in line and line.strip().startswith('|') and line.strip().endswith('|'))  # 表格
                        )
                        
                        # 如果是延续行（不是列表标记，不是特殊格式，且不是空行），合并到前一个列表项
                        # 条件：缩进大于等于列表项缩进，或者 parabuf 为空（紧跟在列表项后面）
                        if not is_list_marker and not is_special_format and line_stripped:
                            # 检查缩进：如果缩进大于列表项缩进，或者是紧跟在列表项后面（parabuf为空）
                            if (line_indent > list_indent) or (not parabuf and line_indent >= list_indent):
                                # 这是列表项的延续内容，合并到前一个列表项
                                last_item_text = last_item[1] if len(last_item) > 1 else ""
                                # 更新列表项文本，添加换行和延续内容
                                new_item_text = last_item_text + "\n" + line_stripped
                                # 替换最后一个 item
                                last_items[-1] = ('list_item', new_item_text, list_indent, last_item[3] if len(last_item) > 3 else False)
                                i += 1
                                continue
            
            # 普通文本
            parabuf.append(line)
            i += 1
        
        # 收尾
        flush_para_buffer(parabuf)
        if in_code:
            (cur['items'] if cur else preface).append(('code', '\n'.join(buf_code), code_lang))
        if in_formula:
            (cur['items'] if cur else preface).append(('formula', '\n'.join(buf_formula)))
        
        # 处理列表和表格的分组
        def _group_list_and_table_items(items):
            """将连续的列表项和表格行分组"""
            grouped = []
            i = 0
            while i < len(items):
                item_type, *item_data = items[i]
                
                if item_type == 'list_item':
                    # 收集连续的列表项
                    current_list = []
                    list_indent = item_data[1] if len(item_data) > 1 else 0
                    list_ordered = item_data[2] if len(item_data) > 2 else False
                    
                    while i < len(items):
                        item_type, *item_data = items[i]
                        if item_type != 'list_item':
                            break
                        indent = item_data[1] if len(item_data) > 1 else 0
                        is_ordered = item_data[2] if len(item_data) > 2 else False
                        
                        # 如果是新的列表（不同的缩进或类型），结束当前列表
                        if indent < list_indent or (indent == list_indent and is_ordered != list_ordered):
                            break
                        
                        current_list.append((item_data[0], indent))
                        i += 1
                    
                    # 递归处理嵌套列表（传入基础缩进级别）
                    nested_list = self._build_list_structure(current_list, list_indent, list_ordered)
                    grouped.append(('list', nested_list, list_ordered))
                    continue
                
                elif item_type == 'table_row' or item_type == 'table_separator':
                    # 收集表格行
                    table_rows = []
                    table_alignments = ['left']  # 默认对齐
                    is_header = True  # 第一行默认为表头
                    
                    # 收集表格行，处理分隔行
                    j = i
                    while j < len(items):
                        item_type_check, *item_data_check = items[j]
                        if item_type_check == 'table_separator':
                            # 分隔行用于确定对齐方式，不添加到 table_rows
                            table_alignments = item_data_check[0] if len(item_data_check) > 0 else ['left']
                            j += 1
                            continue
                        elif item_type_check == 'table_row':
                            table_rows.append((item_data_check[0] if len(item_data_check) > 0 else [], is_header))
                            is_header = False  # 后续行为数据行
                            j += 1
                        else:
                            break
                    
                    if table_rows:
                        grouped.append(('table', table_rows, table_alignments))
                    i = j
                    continue
                
                else:
                    grouped.append(items[i])
                    i += 1
            
            return grouped
        
        # 对每个 section 的 items 进行分组
        for sec in sections:
            sec['items'] = _group_list_and_table_items(sec['items'])
        if preface:
            preface = _group_list_and_table_items(preface)
        if cur:
            cur['items'] = _group_list_and_table_items(cur['items'])
        
        if cur:
            sections.append(cur)
        elif preface:
            # 如果只有卷首语，没有 H3，创建一个无标题的章节
            sections.append({'level': 0, 'title': '', 'items': preface})
        
        # 交给 _convert_section 渲染
        html = []
        for sec in sections:
            html.append(self._convert_section(sec['level'], sec['title'], sec['items']))
        
        # 清理临时资源
        self.formula_processor.cleanup_temp_files()
        self.mermaid_processor.cleanup_temp_files()
        return ''.join(html)
    
    def _convert_section(self, level: int, title: str, content: List[Tuple]) -> str:
        """转换单个章节为 HTML（H2 和 H3 都可以作为分块）"""
        html_parts = []
        
        # 检测是否为参考文献部分
        is_reference_section = False
        if title:
            title_lower = title.strip().lower()
            # 支持多种参考文献标题格式
            reference_keywords = ['参考文献', 'references', '参考', 'reference', 'bibliography', 'bibliographies']
            is_reference_section = any(keyword in title_lower for keyword in reference_keywords)
        
        # 输出标题
        if title and level > 0:
            html_parts.append(self._convert_heading(title, level))
        
        # 对于H2和H3分块，内容需要用卡片包裹
        if level == 2 or level == 3:
            # H2和H3内容用卡片包裹，使用主题背景色（80%透明度）
            # 但如果没有实际内容（只有空行），则不添加卡片
            card_content = []
            has_real_content = False  # 标记是否有实际内容（不包括空行）
            
            # 检查第一个非空内容项是否是图片（用于判断是否在标题附近）
            first_real_item_idx = -1
            for idx, (item_type, *item_data) in enumerate(content):
                # 跳过空项和空段落
                if item_type == "empty":
                    continue
                if item_type == "paragraph":
                    para_text = item_data[0] if len(item_data) > 0 else ""
                    if para_text.strip():
                        first_real_item_idx = idx
                        break
                else:
                    # 其他类型（heading, code, image, formula, mermaid, list, table等）
                    first_real_item_idx = idx
                    break
            
            is_first_image = (first_real_item_idx >= 0 and 
                            len(content) > first_real_item_idx and 
                            content[first_real_item_idx][0] == "image")
            
            for idx, (item_type, *item_data) in enumerate(content):
                if item_type == "heading":
                    # 子标题（H4+）
                    heading_text = item_data[0] if len(item_data) > 0 else ""
                    heading_level = item_data[1] if len(item_data) > 1 else 4
                    card_content.append(self._convert_heading(heading_text, heading_level, is_reference_section))
                    has_real_content = True
                elif item_type == "paragraph":
                    # 段落：检查是否为空或只包含空白
                    para_text = item_data[0] if len(item_data) > 0 else ""
                    if para_text.strip():
                        card_content.append(self._convert_paragraph(para_text, is_reference_section))
                        has_real_content = True
                elif item_type == "code":
                    code_content, code_language = item_data[0], item_data[1] if len(item_data) > 1 else ""
                    card_content.append(self.code_formatter.format_code_block(code_content, code_language))
                    has_real_content = True
                elif item_type == "image":
                    src = item_data[0] if len(item_data) > 0 else ""
                    alt = item_data[1] if len(item_data) > 1 else ""
                    title = item_data[2] if len(item_data) > 2 else ""
                    # 正文中的图片（包括标题附近的图片）都从1开始编号
                    self.image_counter += 1
                    card_content.append(self.image_processor.process_image(src, alt, title, self.image_counter))
                    has_real_content = True
                elif item_type == "formula":
                    # 块级公式已经包含米黄色背景和正确的<div>标签，直接使用
                    formula_html = self.formula_processor.format_block_formula(item_data[0])
                    card_content.append(formula_html)
                    has_real_content = True
                elif item_type == "mermaid":
                    card_content.append(self.mermaid_processor.format_mermaid(item_data[0]))
                    has_real_content = True
                elif item_type == "list":
                    list_structure, is_ordered = item_data[0] if len(item_data) > 0 else [], item_data[1] if len(item_data) > 1 else False
                    if list_structure:  # 只有当列表不为空时才添加
                        card_content.append(self._convert_list(list_structure, is_ordered, is_reference_section))
                        has_real_content = True
                elif item_type == "table":
                    table_rows, alignments = item_data[0] if len(item_data) > 0 else [], item_data[1] if len(item_data) > 1 else ['left']
                    if table_rows:  # 只有当表格不为空时才添加
                        card_content.append(self._convert_table(table_rows, alignments, is_reference_section))
                        has_real_content = True
                elif item_type == "horizontal_rule":
                    card_content.append(self._convert_horizontal_rule())
                    has_real_content = True
                elif item_type == "blockquote":
                    quote_text = item_data[0] if len(item_data) > 0 else ""
                    card_content.append(self._convert_blockquote(quote_text, is_reference_section))
                    has_real_content = True
                # 注意：忽略 "empty" 类型，不标记为实际内容
            
            # 只有当有实际内容时才将内容包裹在卡片中
            if has_real_content and card_content:
                # 如果是参考文献部分，添加小字体和浅色样式
                if is_reference_section:
                    # 参考文献部分：小字体（0.85em）和浅色（#888888）
                    card_html = f'<div style="background-color:{self.style_config.h2_h3_card_bg_color};border:1px solid {self.style_config.h2_h3_card_border_color};border-radius:8px;padding:12px 14px;margin:10px 0;line-height:1.9;font-size:0.85em;color:#888888;">{"".join(card_content)}</div>'
                else:
                    card_html = f'<div style="background-color:{self.style_config.h2_h3_card_bg_color};border:1px solid {self.style_config.h2_h3_card_border_color};border-radius:8px;padding:12px 14px;margin:10px 0;line-height:1.9;">{"".join(card_content)}</div>'
                html_parts.append(card_html)
        else:
            # 其他分块（如卷首语），正常输出内容
            # 卷首语中的图片不编号
            # 如果是参考文献部分，需要添加包装样式
            if is_reference_section:
                reference_content = []
                for item_type, *item_data in content:
                    if item_type == "heading":
                        # 子标题（H4+）
                        heading_text = item_data[0] if len(item_data) > 0 else ""
                        heading_level = item_data[1] if len(item_data) > 1 else 4
                        reference_content.append(self._convert_heading(heading_text, heading_level, is_reference_section))
                    elif item_type == "paragraph":
                        reference_content.append(self._convert_paragraph(item_data[0], is_reference_section))
                        reference_content.append(self._convert_heading(heading_text, heading_level))
                    elif item_type == "code":
                        code_content, code_language = item_data[0], item_data[1] if len(item_data) > 1 else ""
                        reference_content.append(self.code_formatter.format_code_block(code_content, code_language))
                    elif item_type == "image":
                        src = item_data[0] if len(item_data) > 0 else ""
                        alt = item_data[1] if len(item_data) > 1 else ""
                        title = item_data[2] if len(item_data) > 2 else ""
                        # 卷首语中的图片不编号（传入 0）
                        reference_content.append(self.image_processor.process_image(src, alt, title, 0))
                    elif item_type == "formula":
                        reference_content.append(self.formula_processor.format_block_formula(item_data[0]))
                    elif item_type == "mermaid":
                        reference_content.append(self.mermaid_processor.format_mermaid(item_data[0]))
                    elif item_type == "list":
                        list_structure, is_ordered = item_data[0] if len(item_data) > 0 else [], item_data[1] if len(item_data) > 1 else False
                        reference_content.append(self._convert_list(list_structure, is_ordered, is_reference_section))
                    elif item_type == "table":
                        table_rows, alignments = item_data[0] if len(item_data) > 0 else [], item_data[1] if len(item_data) > 1 else ['left']
                        reference_content.append(self._convert_table(table_rows, alignments, is_reference_section))
                    elif item_type == "horizontal_rule":
                        reference_content.append(self._convert_horizontal_rule())
                    elif item_type == "blockquote":
                        quote_text = item_data[0] if len(item_data) > 0 else ""
                        reference_content.append(self._convert_blockquote(quote_text, is_reference_section))
                    elif item_type == "empty":
                        reference_content.append("<br>")
                # 为参考文献内容添加小字体和浅色样式
                html_parts.append(f'<div style="font-size:0.85em;color:#888888;line-height:1.9;">{"".join(reference_content)}</div>')
            else:
                for item_type, *item_data in content:
                    if item_type == "heading":
                        # 子标题（H4+）
                        heading_text = item_data[0] if len(item_data) > 0 else ""
                        heading_level = item_data[1] if len(item_data) > 1 else 4
                        html_parts.append(self._convert_heading(heading_text, heading_level))
                    elif item_type == "paragraph":
                        html_parts.append(self._convert_paragraph(item_data[0]))
                    elif item_type == "code":
                        code_content, code_language = item_data[0], item_data[1] if len(item_data) > 1 else ""
                        html_parts.append(self.code_formatter.format_code_block(code_content, code_language))
                    elif item_type == "image":
                        src = item_data[0] if len(item_data) > 0 else ""
                        alt = item_data[1] if len(item_data) > 1 else ""
                        title = item_data[2] if len(item_data) > 2 else ""
                        # 卷首语中的图片不编号（传入 0）
                        html_parts.append(self.image_processor.process_image(src, alt, title, 0))
                    elif item_type == "formula":
                        html_parts.append(self.formula_processor.format_block_formula(item_data[0]))
                    elif item_type == "mermaid":
                        html_parts.append(self.mermaid_processor.format_mermaid(item_data[0]))
                    elif item_type == "list":
                        list_structure, is_ordered = item_data[0] if len(item_data) > 0 else [], item_data[1] if len(item_data) > 1 else False
                        html_parts.append(self._convert_list(list_structure, is_ordered))
                    elif item_type == "table":
                        table_rows, alignments = item_data[0] if len(item_data) > 0 else [], item_data[1] if len(item_data) > 1 else ['left']
                        html_parts.append(self._convert_table(table_rows, alignments))
                    elif item_type == "horizontal_rule":
                        html_parts.append(self._convert_horizontal_rule())
                    elif item_type == "blockquote":
                        quote_text = item_data[0] if len(item_data) > 0 else ""
                        html_parts.append(self._convert_blockquote(quote_text))
                    elif item_type == "empty":
                        html_parts.append("<br>")
        
        return "".join(html_parts)
    
    def _convert_heading(self, text: str, level: int, is_reference_section: bool = False) -> str:
        """转换标题"""
        # 根据级别设置样式
        if level == 1:
            # H1 忽略，不显示
            return ''
        elif level == 2:
            # H2 使用粗横线中间为标题的格式
            return f'<div style="text-align:center;margin:20px 0;"><hr style="border:none;border-top:2px solid {self.style_config.h2_title_line_color};margin:0;width:100%;"><span style="background:{self.style_config.card_bg_color};padding:0 15px;position:relative;top:-12px;font-weight:bold;font-size:{self.style_config.h2_title_font_size};color:{self.style_config.h2_title_text_color};">{self._convert_inline_markdown(text, is_reference_section)}</span></div>'
        elif level == 3:
            # H3 使用卡片式样式（作为 H2 的子标题）
            return f'<p style="background-color:{self.style_config.h3_title_bg_color};border-left:4px solid {self.style_config.h3_title_border_color};padding:8px 12px;margin:15px 0;border-radius:4px;"><span style="font-weight:bold;font-size:{self.style_config.h3_title_font_size};color:{self.style_config.h3_title_text_color};">{self._convert_inline_markdown(text, is_reference_section)}</span></p>'
        else:
            # H4+ 使用加粗样式
            return f'<span style="font-weight:bold;color:{self.style_config.card_text_color};">{self._convert_inline_markdown(text, is_reference_section)}</span><br>'
    
    def _convert_paragraph(self, text: str, is_reference_section: bool = False) -> str:
        """转换段落"""
        if not text.strip():
            return ""
        
        # 处理空行：将文本按行分割
        lines = text.split('\n')
        html_lines = []
        prev_line_empty = False
        
        for i, line in enumerate(lines):
            if line.strip():
                # 非空行：转换内联 Markdown
                html_lines.append(self._convert_inline_markdown(line, is_reference_section))
                prev_line_empty = False
            else:
                # 空行：如果前一行不是空行，添加一个 <br>（避免连续空行产生多个换行）
                if not prev_line_empty and i > 0:
                    html_lines.append('<br>')
                prev_line_empty = True
        
        # 合并所有行
        html_text = ''.join(html_lines)
        
        # 检查段落是否以空行结尾
        # 如果最后一行是空行，已经添加了 <br>，不需要再添加
        # 如果最后一行不是空行，添加一个 <br> 作为段落结束
        if lines and lines[-1].strip():
            return f"{html_text}<br>"
        else:
            # 段落以空行结尾，空行已经产生了 <br>，不再添加额外的 <br>
            return html_text
    
    def _convert_horizontal_rule(self) -> str:
        """转换水平分割线"""
        # 使用 <hr> 标签，添加样式使其在微信中正确显示
        # 使用主题颜色作为分割线颜色
        return f'<hr style="border:none;border-top:1px solid {self.style_config.h2_h3_card_border_color};margin:20px 0;width:100%;"><br>'
    
    def _convert_blockquote(self, text: str, is_reference_section: bool = False) -> str:
        """
        转换引用块（blockquote）
        
        Args:
            text: 引用文本
            is_reference_section: 是否在参考文献部分
        
        Returns:
            HTML 字符串（带增强显示效果的引用块）
        """
        if not text.strip():
            return ""
        
        # 转换内联 Markdown 格式
        converted_text = self._convert_inline_markdown(text, is_reference_section)
        
        # 引用块样式：
        # - 左侧添加深色竖条（使用主题颜色）
        # - 浅灰色背景
        # - 斜体文字
        # - 适当的内边距和圆角
        quote_style = (
            f'background-color:rgba(240, 240, 240, 0.6);'
            f'border-left:4px solid {self.style_config.h3_title_border_color};'
            f'padding:12px 16px;'
            f'margin:15px 0;'
            f'border-radius:4px;'
            f'font-style:italic;'
            f'color:{self.style_config.card_text_color};'
            f'line-height:1.8;'
        )
        
        return f'<div style="{quote_style}">{converted_text}</div><br>'
    
    def _build_list_structure(self, items: List[Tuple[str, int]], base_indent: int, is_ordered: bool) -> List:
        """
        构建嵌套列表结构
        
        Args:
            items: [(text, indent), ...] 列表项和缩进
            base_indent: 基础缩进级别
            is_ordered: 是否有序列表
        
        Returns:
            嵌套列表结构 [(text, indent, nested_list?), ...]
        """
        if not items:
            return []
        
        result = []
        i = 0
        
        while i < len(items):
            text, indent = items[i]
            
            # 如果缩进小于基础缩进，说明是上一级列表的项，应该返回
            if indent < base_indent:
                break
            
            # 如果缩进等于基础缩进，这是当前级别的项
            if indent == base_indent:
                # 检查后面是否有嵌套项（缩进更大的项）
                nested_items = []
                j = i + 1
                while j < len(items) and items[j][1] > indent:
                    nested_items.append(items[j])
                    j += 1
                
                if nested_items:
                    # 有嵌套列表，递归构建
                    nested_list = self._build_list_structure(nested_items, indent + 2, is_ordered)
                    result.append((text, indent, nested_list))
                    i = j
                else:
                    # 普通列表项
                    result.append((text, indent))
                    i += 1
            else:
                # 缩进大于基础缩进，但不在处理范围内（应该被前面的递归处理）
                i += 1
        
        return result
    
    def _convert_list_item_with_bold_colon(self, text: str, is_reference_section: bool = False) -> str:
        """
        转换列表项文本
        
        规则：
        1. **加粗文本**：描述 → 应用防换行处理（加粗+冒号）
        2. 普通文本：描述 → 应用防换行处理（无加粗但有冒号）
        3. 普通文本（无冒号） → 正常处理（不需要防换行）
        4. 包含块级公式 $$...$$ → 提取公式并分别渲染
        
        Args:
            text: 列表项文本（Markdown 格式）
        
        Returns:
            HTML 字符串（可能包含多个部分，用特殊标记分隔）
        """
        zw_char = '\u200c\u200d'  # 零宽字符组合
        
        # 先检查是否包含块级公式 $$...$$
        # 使用更精确的正则表达式，匹配 $$...$$ 但不匹配 $$$...$$$ 或更多 $
        formula_match = re.search(r'(?<!\$)\$\$((?:[^$]|\$(?!\$))+)\$\$(?!\$)', text)
        if formula_match:
            # 找到公式，分割文本
            formula_content = formula_match.group(1).strip()
            before_formula = text[:formula_match.start()].rstrip()
            after_formula = text[formula_match.end():].lstrip()
            
            # 检查公式前的文本是否包含加粗+冒号格式
            # 如果包含，公式后的文本应该作为描述部分继续
            bold_colon_pattern = r'(\*\*[^*]+\*\*[：:])(.*)'
            bold_match = re.match(bold_colon_pattern, before_formula)
            
            result_parts = []
            
            if bold_match:
                # 公式前有加粗+冒号格式
                bold_part = bold_match.group(1)  # **text**：
                desc_before = bold_match.group(2).strip()  # 公式前的描述部分
                
                # 处理加粗部分（包含冒号）
                converted_bold = self._convert_inline_markdown(bold_part, is_reference_section, is_in_list_item=True)
                bold_html = converted_bold.replace('</strong>', f'{zw_char}</strong>')
                if '：' in bold_html or ':' in bold_html:
                    bold_html = re.sub(r'(</strong>)([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', bold_html)
                    bold_html = re.sub(r'([^：:])([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', bold_html, count=1)
                
                # 组合：加粗部分 + 公式前的描述 + 公式 + 公式后的描述
                desc_parts = []
                if desc_before:
                    desc_parts.append(self._convert_inline_markdown(desc_before, is_reference_section, is_in_list_item=True))
                
                # 公式（换行显示，块级公式）
                formula_html = self.formula_processor.format_block_formula(formula_content)
                desc_parts.append(formula_html)
                
                # 公式后的文本作为描述部分继续
                if after_formula:
                    desc_parts.append(self._convert_inline_markdown(after_formula, is_reference_section, is_in_list_item=True))
                
                # 组合所有部分
                desc_html = ''.join(desc_parts)
                if desc_before.startswith(' '):
                    desc_html = '&nbsp;' + desc_html
                
                return f'<span style="white-space: nowrap;">{bold_html}</span>&nbsp;{desc_html}'
            else:
                # 公式前没有加粗+冒号格式，检查是否有普通冒号
                colon_pos = -1
                for i, char in enumerate(before_formula):
                    if char in '：:':
                        colon_pos = i
                        break
                
                if colon_pos > 0:
                    # 有冒号，分别处理标题和描述
                    title_part = before_formula[:colon_pos + 1]
                    desc_before = before_formula[colon_pos + 1:].strip()
                    
                    # 处理标题部分
                    converted_title = self._convert_inline_markdown(title_part, is_reference_section, is_in_list_item=True)
                    title_html = re.sub(r'(</\w+>)([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', converted_title)
                    if '：' in title_html or ':' in title_html:
                        title_html = re.sub(r'(</\w+>)([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', title_html)
                        title_html = re.sub(r'([^：:])([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', title_html, count=1)
                    
                    # 组合描述部分
                    desc_parts = []
                    if desc_before:
                        desc_parts.append(self._convert_inline_markdown(desc_before, is_reference_section, is_in_list_item=True))
                    
                    # 公式
                    formula_html = self.formula_processor.format_block_formula(formula_content)
                    desc_parts.append(formula_html)
                    
                    # 公式后的文本
                    if after_formula:
                        desc_parts.append(self._convert_inline_markdown(after_formula, is_reference_section, is_in_list_item=True))
                    
                    desc_html = ''.join(desc_parts)
                    if desc_before.startswith(' '):
                        desc_html = '&nbsp;' + desc_html
                    
                    return f'<span style="white-space: nowrap;">{title_html}</span>&nbsp;{desc_html}'
                else:
                    # 没有冒号，正常处理各部分
                    if before_formula.strip():
                        result_parts.append(self._convert_inline_markdown(before_formula, is_reference_section, is_in_list_item=True))
                    
                    # 公式
                    formula_html = self.formula_processor.format_block_formula(formula_content)
                    result_parts.append(formula_html)
                    
                    # 公式后的文本
                    if after_formula.strip():
                        result_parts.append(self._convert_inline_markdown(after_formula, is_reference_section, is_in_list_item=True))
                    
                    return ''.join(result_parts)
        
        # 没有公式，正常处理
        return self._convert_list_item_text_part(text, zw_char, is_reference_section)
    
    def _convert_list_item_text_part(self, text: str, zw_char: str, is_reference_section: bool = False) -> str:
        """
        转换列表项文本部分（不包含公式）
        
        Args:
            text: 列表项文本（Markdown 格式）
            zw_char: 零宽字符组合
        
        Returns:
            HTML 字符串
        """
        # 匹配模式1：**加粗文本**：描述
        bold_colon_pattern = r'(\*\*[^*]+\*\*[：:])(.*)'
        bold_match = re.match(bold_colon_pattern, text)
        
        if bold_match:
            # 分别处理加粗部分和描述部分
            bold_part = bold_match.group(1)  # **text**：
            desc_part = bold_match.group(2).strip()  # 描述文本
            
            # 转换加粗部分（包含冒号）
            converted_bold = self._convert_inline_markdown(bold_part, is_reference_section, is_in_list_item=True)
            
            # 在 </strong> 和冒号之间插入多个零宽字符，确保冒号不会单独换到下一行
            # 在冒号前插入多个零宽字符，形成更强的防换行连接
            bold_html = converted_bold.replace('</strong>', f'{zw_char}</strong>')
            # 如果冒号不在 strong 标签内，需要在冒号前也插入多个零宽字符
            if '：' in bold_html or ':' in bold_html:
                # 在冒号前插入多个零宽字符，确保冒号不会单独换行
                bold_html = re.sub(r'(</strong>)([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', bold_html)
                # 如果冒号不在标签后，也需要处理
                bold_html = re.sub(r'([^：:])([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', bold_html, count=1)
            
            # 转换描述部分
            if desc_part:
                desc_html = self._convert_inline_markdown(desc_part, is_reference_section, is_in_list_item=True)
                # 只将描述文本的第一个空格替换为 &nbsp;，防止在冒号后立即换行
                # 但描述文本本身可以换行（不包裹在 nowrap 中）
                if desc_part.startswith(' '):
                    desc_html_final = '&nbsp;' + desc_html
                else:
                    desc_html_final = desc_html
                # 只对标题+冒号部分使用 nowrap，确保冒号不会单独换行
                # 描述部分允许自然换行
                return f'<span style="white-space: nowrap;">{bold_html}</span>&nbsp;{desc_html_final}'
            else:
                return f'<span style="white-space: nowrap;">{bold_html}</span>'
        
        # 匹配模式2：普通文本：描述（无加粗但有冒号）
        # 匹配格式：文本（可能包含代码、链接等）：描述
        # 首先检查整个文本是否是一个完整的链接 [text](url)
        # 如果是完整链接，直接转换，不进行冒号分割
        link_pattern = r'^\[([^\]]+)\]\(([^)]+)\)$'
        link_match = re.match(link_pattern, text.strip())
        if link_match:
            # 整个文本是一个完整链接，直接转换（传递 is_in_list_item=True）
            return self._convert_inline_markdown(text, is_reference_section, is_in_list_item=True)
        
        # 查找第一个冒号（中文或英文）的位置
        # 需要排除：
        # 1. URL中的://
        # 2. 链接括号内的冒号
        # 3. 颜色标记中的冒号 {color:
        colon_pos = -1
        in_link = False  # 是否在链接的括号内
        in_color_tag = False  # 是否在颜色标记内
        for i, char in enumerate(text):
            # 检查是否进入颜色标记 {color: 或 {color:
            if i > 0 and text[i-6:i+1] == '{color:':
                in_color_tag = True
            # 检查是否离开颜色标记（遇到}）
            elif in_color_tag and char == '}':
                in_color_tag = False
                continue
            
            # 检查是否进入或离开链接的括号
            if i > 0 and text[i-1] == ']' and char == '(':
                in_link = True
            elif in_link and char == ')':
                in_link = False
                continue
            
            # 如果在链接内或颜色标记内，跳过冒号
            if in_link or in_color_tag:
                continue
            
            # 检查是否是URL协议中的://
            if char in '：:':
                # 检查是否是://的一部分
                if i > 0 and text[i-1] == '/' and i < len(text) - 1 and text[i+1] == '/':
                    continue
                # 检查是否在颜色标记中 {color: 或 {color:
                # 向前查找最多7个字符，看是否是 {color:
                start = max(0, i - 6)
                if text[start:i+1].endswith('{color:'):
                    in_color_tag = True
                    continue
                # 检查冒号是否在链接的方括号内 [text:...](url)
                # 如果冒号前面有 [ 且后面有 ]，说明在链接文本内，不应该分割
                if '[' in text[:i] and ']' in text[i:]:
                    # 检查是否在链接的方括号内
                    last_open_bracket = text.rfind('[', 0, i)
                    if last_open_bracket >= 0:
                        next_close_bracket = text.find(']', i)
                        if next_close_bracket > i:
                            # 冒号在链接的方括号内，跳过
                            continue
                colon_pos = i
                break
        
        if colon_pos > 0:
            # 找到了冒号，分别处理标题部分和描述部分
            title_part = text[:colon_pos + 1]  # text：
            desc_part = text[colon_pos + 1:].strip()  # 描述文本
            
            # 转换标题部分（包含冒号）
            converted_title = self._convert_inline_markdown(title_part, is_reference_section, is_in_list_item=True)
            
            # 在冒号前后插入多个零宽字符，确保冒号不会单独换到下一行
            # 处理 </code>、</strong> 等标签后的冒号
            title_html = re.sub(r'(</\w+>)([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', converted_title)
            # 如果冒号不在标签内，也需要处理
            if '：' in title_html or ':' in title_html:
                # 在冒号前后插入多个零宽字符，确保冒号不会单独换行
                # 先处理标签后的冒号（如果还没有处理）
                title_html = re.sub(r'(</\w+>)([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', title_html)
                # 处理普通文本中的冒号（如果还没有处理）
                title_html = re.sub(r'([^：:])([：:])', lambda m: f'{m.group(1)}{zw_char}{zw_char}{zw_char}{m.group(2)}{zw_char}', title_html, count=1)
            
            # 转换描述部分
            if desc_part:
                desc_html = self._convert_inline_markdown(desc_part, is_reference_section, is_in_list_item=True)
                # 只将描述文本的第一个空格替换为 &nbsp;，防止在冒号后立即换行
                # 但描述文本本身可以换行（不包裹在 nowrap 中）
                if desc_part.startswith(' '):
                    desc_html_final = '&nbsp;' + desc_html
                else:
                    desc_html_final = desc_html
                # 只对标题+冒号部分使用 nowrap，确保冒号不会单独换行
                # 描述部分允许自然换行
                return f'<span style="white-space: nowrap;">{title_html}</span>&nbsp;{desc_html_final}'
            else:
                return f'<span style="white-space: nowrap;">{title_html}</span>'
        
        # 不匹配任何模式，正常转换（无冒号的普通文本）
        return self._convert_inline_markdown(text, is_reference_section, is_in_list_item=True)
    
    def _convert_list(self, list_structure: List, is_ordered: bool, is_reference_section: bool = False) -> str:
        """
        将列表结构转换为 HTML
        
        Args:
            list_structure: 列表结构（由 _build_list_structure 生成）
            is_ordered: 是否有序列表
        
        Returns:
            HTML 字符串
        """
        if not list_structure:
            return ""
        
        tag = "ol" if is_ordered else "ul"
        html_items = []
        
        for item in list_structure:
            # 如果是参考文献部分，为列表项添加不换行样式（横向滚动在容器上）
            if is_reference_section:
                li_style = 'white-space:nowrap;'
            else:
                li_style = ''
            
            if len(item) == 3:
                # 有嵌套列表
                text, indent, nested_list = item
                # 使用特殊处理方法来处理加粗文本+冒号的格式
                converted_text = self._convert_list_item_with_bold_colon(text, is_reference_section)
                nested_html = self._convert_list(nested_list, is_ordered, is_reference_section)
                item_html = f"<li style=\"{li_style}\">{converted_text}{nested_html}</li>"
                html_items.append(item_html)
            else:
                # 普通列表项
                text, indent = item
                # 使用特殊处理方法来处理加粗文本+冒号的格式
                converted_text = self._convert_list_item_with_bold_colon(text, is_reference_section)
                item_html = f"<li style=\"{li_style}\">{converted_text}</li>"
                html_items.append(item_html)
        
        # 如果是参考文献部分，为整个列表容器添加横向滚动样式
        if is_reference_section:
            list_style = "margin:10px 0;padding-left:30px;line-height:1.8;overflow-x:auto;"
        else:
            list_style = "margin:10px 0;padding-left:20px;line-height:1.8;"
        
        list_html = f"<{tag} style=\"{list_style}\">" + "".join(html_items) + f"</{tag}>"
        return list_html
    
    def _convert_table(self, table_rows: List[Tuple], alignments: List[str], is_reference_section: bool = False) -> str:
        """
        将表格转换为 HTML（使用微信兼容的方式，不使用 table 标签）
        
        Args:
            table_rows: [(cells, is_header), ...] 表格行
            alignments: 每列的对齐方式
        
        Returns:
            HTML 字符串
        """
        if not table_rows:
            return ""
        
        html_parts = []
        
        # 计算列宽（简单平均分配）
        num_cols = max(len(row[0]) for row in table_rows) if table_rows else 0
        if num_cols == 0:
            return ""
        
        # 确保对齐方式数量匹配列数
        while len(alignments) < num_cols:
            alignments.append('left')
        
        # 表头样式（只保留字体加粗，背景色移到行容器）
        header_text_style = f"font-weight:bold;"
        # 移除单元格边框，只保留内边距
        cell_style_base = f"padding:8px 12px;"
        
        # 构建表格行
        for row_idx, (cells, is_header) in enumerate(table_rows):
            row_html_parts = []
            
            # 确保单元格数量匹配
            while len(cells) < num_cols:
                cells.append("")
            
            for col_idx, cell_text in enumerate(cells[:num_cols]):
                alignment = alignments[col_idx] if col_idx < len(alignments) else 'left'
                text_align = f"text-align:{alignment};"
                
                # 单元格样式（移除边框，标题栏只保留字体加粗，不设置背景色）
                if is_header:
                    cell_style = f"{cell_style_base}{header_text_style}{text_align}"
                else:
                    cell_style = f"{cell_style_base}{text_align}"
                
                # 转换单元格内容
                cell_content = self._convert_inline_markdown(cell_text, is_reference_section)
                
                # 使用 span 标签模拟表格单元格（微信不支持 table 标签）
                # 注意：使用 flex 或 table-cell 可能不被微信支持，所以使用 inline-block
                # 计算每个单元格的宽度
                # 移除 min-height，让每个单元格根据内容自适应高度
                # 使用 vertical-align:middle 让单元格内容垂直居中
                cell_width = f"{100/num_cols:.2f}%"
                row_html_parts.append(
                    f'<span style="{cell_style}display:inline-block;width:{cell_width};vertical-align:middle;box-sizing:border-box;">{cell_content}</span>'
                )
            
            # 每行用 p 标签包裹，并添加换行
            # 添加行之间的横线（border-bottom），最后一行不添加
            # 如果是标题行，添加背景色到行容器（上下线之间的范围）
            border_bottom = ""
            row_bg = ""
            if row_idx < len(table_rows) - 1:
                border_bottom = f"border-bottom:1px solid {self.style_config.h2_h3_card_border_color};"
            if is_header:
                row_bg = f"background-color:{self.style_config.h3_title_bg_color};"
            
            row_html = f'<p style="margin:0;padding:0;line-height:1.6;width:100%;overflow:hidden;{border_bottom}{row_bg}">{"".join(row_html_parts)}</p>'
            html_parts.append(row_html)
        
        # 用 div 包裹整个表格，只保留顶部和底部边框，移除左右边框
        table_html = f'<div style="border-top:1px solid {self.style_config.h2_h3_card_border_color};border-bottom:1px solid {self.style_config.h2_h3_card_border_color};margin:15px 0;overflow:hidden;">{"".join(html_parts)}</div>'
        return table_html + "<br>"
    
    def _convert_inline_markdown(self, text: str, is_reference_section: bool = False, is_in_list_item: bool = False) -> str:
        """
        转换内联 Markdown（粗体、代码、链接、行内公式等）
        
        Args:
            text: 要转换的文本
            is_reference_section: 是否在参考文献部分（用于特殊处理链接格式）
            is_in_list_item: 是否在列表项中（用于区分列表项和非列表项的链接处理）
        """
        # 使用占位符方法：先处理所有需要生成 HTML 的内容，然后统一转义
        
        # 第一步：处理行内数学公式 $...$（但不处理 $$...$$，因为那是块级公式）
        formula_placeholders = {}
        formula_counter = 0
        
        def replace_inline_formula(match):
            nonlocal formula_counter
            latex = match.group(1)
            # 使用不包含 < > & 的特殊占位符，避免被转义
            placeholder = f"__FORMULA{formula_counter}__"
            try:
                formula_html = self.formula_processor.format_inline_formula(latex)
                formula_placeholders[placeholder] = formula_html
            except Exception as e:
                # 如果渲染失败，输出警告并保留原始公式
                print(f"Warning: Failed to render inline formula '${latex}$': {e}")
                formula_placeholders[placeholder] = f'${latex}$'  # 保留原始公式
            formula_counter += 1
            return placeholder
        
        # 匹配 $...$ 但不匹配 $$...$$
        text = re.sub(r'(?<!\$)\$([^$]+)\$(?!\$)', replace_inline_formula, text)
        
        # 第二步：处理颜色语法（使用占位符方法，避免被转义）
        # 支持以下语法（推荐使用前两种，边界明确）：
        # 1. **文字**{color:#ff0000} - 加粗+颜色（推荐）
        # 2. [文字]{color:#ff0000} - 仅颜色（推荐）
        # 3. {color:#ff0000}文字{/color} - 标签风格的颜色
        
        color_placeholders = {}
        color_counter = 0
        
        def create_color_placeholder(html_content):
            nonlocal color_counter
            placeholder = f"__COLOR{color_counter}__"
            color_placeholders[placeholder] = html_content
            color_counter += 1
            return placeholder
        
        # 首先，清理文本中的零宽字符（这些字符可能干扰正则匹配）
        # 零宽字符包括：
        # - 零宽空格(U+200B)、零宽不连字(U+200C)、零宽连字(U+200D)
        # - 字节序标记(U+FEFF)
        # - 左至右标记(U+200E)、右至左标记(U+200F)
        # - 其他不可见字符
        text = re.sub(r'[\u200B-\u200F\uFEFF\u2060-\u206F]', '', text)
        
        # 处理加粗+颜色组合：**text**{color:#ff0000} 或 **text**{color: #ff0000}
        def replace_bold_color(match):
            content = match.group(1)
            color = match.group(2)
            # 验证颜色格式（支持 #rrggbb, rgb(r,g,b), 颜色名称）
            color_style = self._validate_color(color)
            if color_style:
                html = f'<strong><span style="{color_style}">{content}</span></strong>'
                return create_color_placeholder(html)
            else:
                # 如果颜色无效，只保留加粗，不创建占位符
                return f'**{content}**'
        
        # 允许 color: 后面有可选的空格
        text = re.sub(r'\*\*([^*]+)\*\*\{color:\s*([^}]+)\}', replace_bold_color, text)
        
        # 处理仅颜色：[text]{color:#ff0000} 或 [text]{color: #ff0000}
        def replace_color_only(match):
            content = match.group(1)
            color = match.group(2)
            color_style = self._validate_color(color)
            if color_style:
                html = f'<span style="{color_style}">{content}</span>'
                return create_color_placeholder(html)
            else:
                # 如果颜色无效，返回原文本
                return match.group(0)
        
        # 允许 color: 后面有可选的空格
        text = re.sub(r'\[([^\]]+)\]\{color:\s*([^}]+)\}', replace_color_only, text)
        
        # 处理标签风格的颜色：{color:#ff0000}text{/color} 或 {color: #ff0000}text{/color}
        def replace_color_tag(match):
            content = match.group(2)  # 注意：第二个是内容
            color = match.group(1)    # 第一个是颜色
            color_style = self._validate_color(color)
            if color_style:
                html = f'<span style="{color_style}">{content}</span>'
                return create_color_placeholder(html)
            else:
                # 如果颜色无效，返回原文本
                return match.group(0)
        
        # 允许 color: 后面有可选的空格
        text = re.sub(r'\{color:\s*([^}]+)\}([^{]+)\{/color\}', replace_color_tag, text)
        
        # 第三步：处理 HTML 标签（如 <br>, <br/>）使用占位符，避免被转义
        html_tag_placeholders = {}
        html_tag_counter = 0
        
        def replace_html_tag(match):
            nonlocal html_tag_counter
            tag = match.group(0)  # 完整的标签，如 <br> 或 <br/>
            placeholder = f"__HTMLTAG{html_tag_counter}__"
            html_tag_placeholders[placeholder] = tag
            html_tag_counter += 1
            return placeholder
        
        # 匹配常见的 HTML 标签（如 <br>, <br/>, <br />, <p>, </p> 等）
        # 但只匹配简单的自闭合标签和换行标签，避免匹配复杂的标签
        text = re.sub(r'<(br\s*/?|p\s*/?|/p\s*|div\s*/?|/div\s*|span\s*/?|/span\s*)>', replace_html_tag, text, flags=re.IGNORECASE)
        
        # 第三步：处理 HTML 标签（如 <br>, <br/>）使用占位符，避免被转义
        html_tag_placeholders = {}
        html_tag_counter = 0
        
        def replace_html_tag(match):
            nonlocal html_tag_counter
            tag = match.group(0)  # 完整的标签，如 <br> 或 <br/>
            placeholder = f"__HTMLTAG{html_tag_counter}__"
            html_tag_placeholders[placeholder] = tag
            html_tag_counter += 1
            return placeholder
        
        # 匹配常见的 HTML 标签（如 <br>, <br/>, <br />, <p>, </p> 等）
        # 但只匹配简单的自闭合标签和换行标签，避免匹配复杂的标签
        text = re.sub(r'<(br\s*/?|p\s*/?|/p\s*|div\s*/?|/div\s*|span\s*/?|/span\s*)>', replace_html_tag, text, flags=re.IGNORECASE)
        
        # 第四步：转义 HTML 特殊字符
        # 先转义 &，但要避免转义已生成的 HTML 实体
        text = text.replace("&", "&amp;")
        # 转义 < 和 >
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        
        # 第五步：恢复 HTML 标签占位符
        for placeholder, tag in html_tag_placeholders.items():
            text = text.replace(placeholder, tag)
        
        # 第六步：处理其他 Markdown 语法
        # 处理粗体 **text**（双星号，不会与占位符冲突，且未被颜色处理匹配）
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        
        # 处理斜体 *text* 或 _text_
        text = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'<em>\1</em>', text)
        text = re.sub(r'(?<!_)_(?!_)([^_]+)_(?!_)', r'<em>\1</em>', text)
        
        # 处理行内代码 `code`
        text = re.sub(r'`([^`]+)`', r'<span style="font-family:monospace;">\1</span>', text)
        
        # 处理链接 [text](url) 或 [text](url "title")
        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2).strip()
            title = match.group(3) if len(match.groups()) > 2 and match.group(3) else None
            
            # 清理URL中的零宽字符（可能在之前处理中被插入）
            # 零宽字符：零宽不连字(U+200C)、零宽空格(U+200B)、零宽连字(U+200D)
            import re
            url_cleaned = re.sub(r'[\u200B-\u200D\uFEFF]', '', url)
            # 清理协议和URL之间的空格（如 "https: //" -> "https://"）
            url_cleaned = re.sub(r'(https?):\s*//', r'\1://', url_cleaned)
            # 清理开头的多余空格和斜杠
            url_cleaned = url_cleaned.lstrip().lstrip('/')
            # 如果清理后没有协议，尝试添加 https://
            if not url_cleaned.startswith(('http://', 'https://')):
                if url_cleaned.startswith('mp.weixin.qq.com'):
                    url_cleaned = 'https://' + url_cleaned
                elif '://' not in url_cleaned:
                    url_cleaned = 'https://' + url_cleaned.lstrip('/')
            
            # 如果是参考文献部分，先检查是否是微信内部链接（在URL编码之前检查）
            # 检查URL中是否包含 mp.weixin.qq.com/s（支持 http/https，支持查询参数）
            is_wechat_link = False
            if is_reference_section:
                is_wechat_link = (
                    'mp.weixin.qq.com' in url_cleaned
                )
            
            # URL 转义：确保 URL 中的特殊字符被正确编码
            # 但保持已有的编码不变
            import urllib.parse
            # 使用清理后的URL进行编码
            # 检查 URL 是否已经是编码过的（简单判断）
            if '%' in url_cleaned and any(c in url_cleaned for c in ['%20', '%2F', '%3A', '%3F']):
                # 可能已经编码过，直接使用
                escaped_url = url_cleaned
            else:
                # 对 URL 进行编码，但保留协议部分
                try:
                    parsed = urllib.parse.urlparse(url_cleaned)
                    if parsed.scheme:
                        # 有协议，只编码路径、查询字符串等部分
                        path = urllib.parse.quote(parsed.path, safe='/')
                        query = urllib.parse.quote(parsed.query, safe='&=')
                        fragment = urllib.parse.quote(parsed.fragment, safe='')
                        escaped_url = f"{parsed.scheme}://{parsed.netloc}{path}"
                        if query:
                            escaped_url += f"?{query}"
                        if fragment:
                            escaped_url += f"#{fragment}"
                    else:
                        # 无协议，直接编码（但保留常见字符）
                        escaped_url = urllib.parse.quote(url_cleaned, safe='/:?=&')
                except:
                    # 如果解析失败，直接转义特殊字符
                    escaped_url = url_cleaned.replace('&', '&amp;').replace('"', '&quot;').replace("'", '&#39;')
            
            # 构建链接 HTML（link_text 已经在前面转义过 HTML 特殊字符）
            # 添加微信兼容的样式：蓝色链接，下划线
            link_style = 'color:#576b95;text-decoration:underline;'
            
            # 如果是参考文献部分且在列表项中，只显示文本和URL，不使用链接
            if is_reference_section and is_in_list_item:
                if is_wechat_link:
                    # 微信内部链接：只显示链接文本，不显示URL
                    # 在链接文本中的冒号前后添加零宽字符，防止换行
                    zw_char = '\u200B\u200C\u200D'  # 零宽字符组合
                    link_text_processed = link_text
                    # 在冒号前后插入零宽字符，防止换行
                    link_text_processed = re.sub(r'([：:])', lambda m: f'{zw_char}{m.group(1)}{zw_char}', link_text_processed)
                    return f'{link_text_processed}'
                else:
                    # 外部链接：显示"名称（URL）"格式，不使用链接
                    # 转义URL用于显示（转义HTML特殊字符，使用清理后的URL）
                    display_url = (url_cleaned.replace('&', '&amp;')
                                  .replace('<', '&lt;')
                                  .replace('>', '&gt;')
                                  .replace('"', '&quot;')
                                  .replace("'", '&#39;'))
                    return f'{link_text}（{display_url}）'
            else:
                # 非列表项或非参考文献部分，使用 <a> 标签
                if is_reference_section and is_wechat_link:
                    # 参考文献部分的微信内部链接：在链接文本中的冒号前后添加零宽字符，防止换行
                    zw_char = '\u200B\u200C\u200D'  # 零宽字符组合
                    link_text_processed = link_text
                    # 在冒号前后插入零宽字符，防止换行
                    link_text_processed = re.sub(r'([：:])', lambda m: f'{zw_char}{m.group(1)}{zw_char}', link_text_processed)
                    # 使用 nowrap 样式防止链接文本换行
                    link_style_nowrap = link_style + 'white-space:nowrap;'
                    if title:
                        escaped_title = title.replace('"', '&quot;').replace("'", '&#39;')
                        return f'<a href="{escaped_url}" title="{escaped_title}" style="{link_style_nowrap}">{link_text_processed}</a>'
                    else:
                        return f'<a href="{escaped_url}" style="{link_style_nowrap}">{link_text_processed}</a>'
                else:
                    # 其他情况：正常使用 <a> 标签
                    if title:
                        escaped_title = title.replace('"', '&quot;').replace("'", '&#39;')
                        return f'<a href="{escaped_url}" title="{escaped_title}" style="{link_style}">{link_text}</a>'
                    else:
                        return f'<a href="{escaped_url}" style="{link_style}">{link_text}</a>'
        
        # 匹配 [text](url "title") 或 [text](url)
        # 先匹配带标题的（更具体，使用非贪婪匹配）
        text = re.sub(r'\[([^\]]+)\]\(([^)]+?)\s+"([^"]+)"\)', replace_link, text)
        # 再匹配不带标题的
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, text)
        
        # 第四步：恢复占位符（在转义后恢复，这样 HTML 不会被转义）
        # 先恢复颜色占位符
        for placeholder, color_html in color_placeholders.items():
            text = text.replace(placeholder, color_html)
        # 再恢复公式占位符
        for placeholder, formula_html in formula_placeholders.items():
            text = text.replace(placeholder, formula_html)
        
        # 第五步：处理粗体 __text__（在占位符恢复后，避免匹配占位符）
        # 使用负向前瞻，确保不匹配已恢复的公式 HTML
        text = re.sub(r'__(?!FORMULA\d+__)([^_]+)__', r'<strong>\1</strong>', text)
        
        # 第六步：处理行尾两个空格（Markdown 硬换行）
        # 将行尾的两个或更多空格转换为 <br>
        text = re.sub(r'  +$', '<br>', text, flags=re.MULTILINE)
        
        return text
    
    def _validate_color(self, color: str) -> str:
        """
        验证并格式化颜色值
        
        Args:
            color: 颜色值（支持 #rrggbb, rgb(r,g,b), rgba(r,g,b,a), 颜色名称）
        
        Returns:
            格式化的 CSS color 样式字符串，如果无效返回空字符串
        """
        color = color.strip()
        
        # 检查是否是有效的颜色格式
        # 支持 #rrggbb 或 #rgb
        if re.match(r'^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$', color):
            return f'color:{color};'
        
        # 支持 rgb(r, g, b) 或 rgba(r, g, b, a)
        if re.match(r'^rgba?\([^)]+\)$', color):
            return f'color:{color};'
        
        # 支持常见颜色名称（英文）
        color_names = {
            'red', 'green', 'blue', 'yellow', 'orange', 'purple', 'pink',
            'brown', 'black', 'white', 'gray', 'grey', 'cyan', 'magenta',
            'lime', 'navy', 'olive', 'teal', 'aqua', 'maroon', 'silver',
            'gold', 'crimson', 'indigo', 'violet', 'coral', 'salmon',
            'tomato', 'chocolate', 'khaki', 'plum', 'turquoise'
        }
        if color.lower() in color_names:
            return f'color:{color};'
        
        # 如果都不匹配，尝试直接使用（可能是有效的 CSS 颜色值）
        # 但为了安全，只允许字母、数字、#、括号、逗号、空格、点
        if re.match(r'^[a-zA-Z0-9#(),.\s-]+$', color) and len(color) <= 50:
            return f'color:{color};'
        
        # 无效颜色，返回空字符串
        return ''
    
    def _generate_html(self, title: str, date: str, tags: List[str], body: str, source: str = "gnss.ac.cn", permalink: str = "") -> str:
        """
        生成完整 HTML
        
        Args:
            title: 文章标题
            date: 发布日期
            tags: 标签列表
            body: 正文 HTML
            source: 来源信息（默认：gnss.ac.cn）
            permalink: 永久链接（可选）
        """
        # 标题条
        header_html = f'''<p style="background-color:{self.style_config.header_bg_color};color:{self.style_config.header_text_color};font-weight:bold;font-size:{self.style_config.header_font_size};line-height:1.6;padding:12px 14px;border-radius:10px 10px 0 0;margin:0;">
  {self._escape_html(title)}
</p>'''
        
        # 标签字符串
        tags_str = " / ".join(tags) if tags else ""
        
        # 元信息
        meta_html = f'<span style="color:{self.style_config.meta_text_color};font-size:{self.style_config.meta_font_size};">日期：{date}　标签：{tags_str}</span><br><br>'
        
        # 构建文尾信息（来源 + permalink）
        footer_parts = []
        footer_parts.append(f'<span style="color:{self.style_config.source_text_color};font-size:{self.style_config.source_font_size};">来源：{self._escape_html(source)}《{self._escape_html(title)}》</span>')
        
        # 如果有 permalink，添加链接
        if permalink:
            # 转义 URL（但保留协议和基本结构）
            import urllib.parse
            try:
                parsed = urllib.parse.urlparse(permalink)
                if parsed.scheme:
                    # 有协议，只编码路径、查询字符串等部分
                    path = urllib.parse.quote(parsed.path, safe='/')
                    query = urllib.parse.quote(parsed.query, safe='&=')
                    fragment = urllib.parse.quote(parsed.fragment, safe='')
                    escaped_url = f"{parsed.scheme}://{parsed.netloc}{path}"
                    if query:
                        escaped_url += f"?{query}"
                    if fragment:
                        escaped_url += f"#{fragment}"
                else:
                    # 无协议，直接编码（但保留常见字符）
                    escaped_url = urllib.parse.quote(permalink, safe='/:?=&')
            except:
                # 如果解析失败，直接转义特殊字符
                escaped_url = permalink.replace('&', '&amp;').replace('"', '&quot;').replace("'", '&#39;')
            
            link_style = 'color:#576b95;text-decoration:underline;'
            footer_parts.append(f'<br><br><a href="{escaped_url}" style="{link_style}font-size:{self.style_config.source_font_size};">原文链接：{self._escape_html(permalink)}</a>')
        
        footer_html = "".join(footer_parts)
        
        # 主卡片
        card_style = f'border:1px solid {self.style_config.card_border_color};border-top:none;border-radius:0 0 10px 10px;background-color:{self.style_config.card_bg_color};color:{self.style_config.card_text_color};line-height:1.9;padding:14px;margin:0;'
        
        card_html = f'''<p style="{card_style}">
  {meta_html}
  {body}
  
  {footer_html}
</p>'''
        
        return header_html + "\n\n" + card_html
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        return (text.replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;")
                  .replace('"', "&quot;")
                  .replace("'", "&#39;"))


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Markdown 转微信公众号 HTML 转换器")
    parser.add_argument("input", help="输入的 Markdown 文件路径")
    parser.add_argument("-o", "--output", help="输出的 HTML 文件路径（默认：输入文件名.html）")
    parser.add_argument("-s", "--style", default="academic_gray", 
                       choices=list(STYLES.keys()),
                       help="风格选择（默认：academic_gray）")
    parser.add_argument("--source", help="来源信息（可选，如果提供则覆盖 Front Matter tags 中的来源，默认：gnss.ac.cn）")
    
    args = parser.parse_args()
    
    # 确定输出文件路径
    if args.output:
        output_path = args.output
    else:
        input_path = Path(args.input)
        output_path = input_path.with_suffix(".html")
    
    # 转换
    base_dir = str(Path(args.input).parent)
    converter = WeChatHTMLConverter(style=args.style, base_dir=base_dir)
    html_content = converter.convert(args.input, source=args.source)
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"转换完成！输出文件: {output_path}")


if __name__ == "__main__":
    main()

