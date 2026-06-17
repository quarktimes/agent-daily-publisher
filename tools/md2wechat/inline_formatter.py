"""
Pygments formatter for inline styles (WeChat compatible)
"""
from pygments.formatters import HtmlFormatter
from pygments.token import Token


class InlineStyleFormatter(HtmlFormatter):
    """Pygments formatter that outputs inline styles instead of CSS classes"""
    
    def __init__(self, **options):
        # 禁用 CSS，使用内联样式
        options['nowrap'] = True
        super().__init__(**options)
    
    def _get_color_style(self, token_type):
        """获取颜色样式"""
        # 定义颜色方案（适合代码高亮）
        # 使用字符串匹配，因为 token_type 是 Token 类的实例
        token_str = str(token_type)
        
        # 关键字
        if token_str.startswith('Token.Keyword'):
            if 'Type' in token_str:
                return 'color:#0000FF;'  # 蓝色
            elif 'Constant' in token_str:
                return 'color:#AF00DB;'  # 紫色
            else:
                return 'color:#0000FF;'  # 蓝色
        # 字符串
        elif token_str.startswith('Token.String'):
            return 'color:#008000;'  # 绿色
        # 注释
        elif token_str.startswith('Token.Comment'):
            return 'color:#008000;'  # 绿色
        # 数字
        elif token_str.startswith('Token.Literal.Number') or token_str.startswith('Token.Number'):
            return 'color:#098658;'  # 深绿色
        # 函数名
        elif token_str == 'Token.Name.Function':
            return 'color:#795E26;'  # 棕色
        # 变量名
        elif token_str.startswith('Token.Name'):
            if token_str == 'Token.Name':
                return 'color:#001080;'  # 深蓝色
            else:
                return ''  # 其他 Name 类型保持默认
        # 操作符
        elif token_str.startswith('Token.Operator'):
            return 'color:#000000;'  # 黑色
        # 标点
        elif token_str == 'Token.Punctuation':
            return 'color:#000000;'  # 黑色
        # 错误
        elif token_str.startswith('Token.Error'):
            return 'color:#FF0000;'  # 红色
        
        return ''  # 默认无颜色
    
    def format(self, tokensource, outfile):
        """格式化 tokens 为 HTML"""
        for ttype, value in tokensource:
            # 获取样式
            style = self._get_color_style(ttype)
            
            # 转义 HTML 特殊字符
            value = (value
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&#39;"))
            
            # 处理换行
            if '\n' in value:
                parts = value.split('\n')
                for i, part in enumerate(parts):
                    if i > 0:
                        outfile.write('<br>')
                    if part:
                        if style:
                            outfile.write(f'<span style="{style}">{part}</span>')
                        else:
                            outfile.write(part)
            else:
                if value:
                    if style:
                        outfile.write(f'<span style="{style}">{value}</span>')
                    else:
                        outfile.write(value)

