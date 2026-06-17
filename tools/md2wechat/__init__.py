"""
Markdown to WeChat HTML Converter

将 Markdown 文件转换为微信公众号兼容的 HTML 格式。
"""

__version__ = "1.0.0"
__author__ = "Mapoet"

from .md2wechat import WeChatHTMLConverter

__all__ = ['WeChatHTMLConverter']

