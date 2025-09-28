"""
Markdown to HTML converter for AI responses.
Supports common markdown formatting used by AI models.
"""
import re
from typing import List


class MarkdownToHtmlConverter:
    """Convert markdown text to HTML with support for common AI formatting patterns."""
    
    def __init__(self, is_email_format=False):
        self.is_email_format = is_email_format
        # Compile regex patterns for better performance
        self.patterns = {
            # Text formatting
            'bold': re.compile(r'\*\*(.*?)\*\*'),
            'italic': re.compile(r'\*(.*?)\*'),
            'code_inline': re.compile(r'`([^`]+)`'),
            'strikethrough': re.compile(r'~~(.*?)~~'),
            
            # Headers
            'header1': re.compile(r'^# (.+)$', re.MULTILINE),
            'header2': re.compile(r'^## (.+)$', re.MULTILINE),
            'header3': re.compile(r'^### (.+)$', re.MULTILINE),
            'header4': re.compile(r'^#### (.+)$', re.MULTILINE),
            
            # Lists
            'unordered_list': re.compile(r'^[*\-+] (.+)$', re.MULTILINE),
            'ordered_list': re.compile(r'^(\d+)\. (.+)$', re.MULTILINE),
            
            # Links
            'link': re.compile(r'\[([^\]]+)\]\(([^)]+)\)'),
            'auto_link': re.compile(r'https?://[^\s<>"{}|^`[\]\\]+'),
            
            # Code blocks
            'code_block': re.compile(r'```(\w+)?\n(.*?)\n```', re.DOTALL),
            'code_block_simple': re.compile(r'```\n?(.*?)\n?```', re.DOTALL),
            
            # Quotes
            'blockquote': re.compile(r'^> (.+)$', re.MULTILINE),
            
            # Horizontal rule
            'hr': re.compile(r'^---+$', re.MULTILINE),
            
            # Line breaks
            'line_break': re.compile(r'\n\n+'),
            'single_break': re.compile(r'(?<!\n)\n(?!\n)'),
        }
    
    def convert(self, markdown: str) -> str:
        """Convert markdown text to HTML."""
        if not markdown or not isinstance(markdown, str):
            return ""
        
        html = markdown.strip()
        
        # Convert code blocks first (to avoid conflicts with other patterns)
        html = self._convert_code_blocks(html)
        
        # Convert headers
        html = self._convert_headers(html)
        
        # Convert lists
        html = self._convert_lists(html)
        
        # Convert blockquotes
        html = self._convert_blockquotes(html)
        
        # Convert links
        html = self._convert_links(html)
        
        # Convert text formatting
        html = self._convert_text_formatting(html)
        
        # Convert horizontal rules
        html = self.patterns['hr'].sub('<hr>', html)
        
        # Convert line breaks
        html = self._convert_line_breaks(html)
        
        # Apply email styles if needed
        if self.is_email_format:
            html = self._apply_email_styles(html)
        
        return html.strip()
    
    def _convert_code_blocks(self, text: str) -> str:
        """Convert code blocks with syntax highlighting classes."""
        # Multi-line code blocks with language
        def replace_code_block(match):
            language = match.group(1) or 'text'
            code = match.group(2).strip()
            escaped_code = self._escape_html(code)
            return f'<pre><code class="language-{language}">{escaped_code}</code></pre>'
        
        text = self.patterns['code_block'].sub(replace_code_block, text)
        
        # Simple code blocks without language
        def replace_simple_code_block(match):
            code = match.group(1).strip()
            escaped_code = self._escape_html(code)
            return f'<pre><code>{escaped_code}</code></pre>'
        
        text = self.patterns['code_block_simple'].sub(replace_simple_code_block, text)
        
        return text
    
    def _convert_headers(self, text: str) -> str:
        """Convert markdown headers to HTML."""
        text = self.patterns['header4'].sub(r'<h4>\1</h4>', text)
        text = self.patterns['header3'].sub(r'<h3>\1</h3>', text)
        text = self.patterns['header2'].sub(r'<h2>\1</h2>', text)
        text = self.patterns['header1'].sub(r'<h1>\1</h1>', text)
        return text
    
    def _convert_lists(self, text: str) -> str:
        """Convert markdown lists to HTML."""
        lines = text.split('\n')
        result = []
        in_ul = False
        in_ol = False
        
        for line in lines:
            # Check for unordered list
            ul_match = self.patterns['unordered_list'].match(line)
            if ul_match:
                if not in_ul:
                    if in_ol:
                        result.append('</ol>')
                        in_ol = False
                    result.append('<ul>')
                    in_ul = True
                result.append(f'<li>{ul_match.group(1)}</li>')
                continue
            
            # Check for ordered list
            ol_match = self.patterns['ordered_list'].match(line)
            if ol_match:
                if not in_ol:
                    if in_ul:
                        result.append('</ul>')
                        in_ul = False
                    result.append('<ol>')
                    in_ol = True
                result.append(f'<li>{ol_match.group(2)}</li>')
                continue
            
            # Not a list item
            if in_ul:
                result.append('</ul>')
                in_ul = False
            if in_ol:
                result.append('</ol>')
                in_ol = False
            
            result.append(line)
        
        # Close any open lists
        if in_ul:
            result.append('</ul>')
        if in_ol:
            result.append('</ol>')
        
        return '\n'.join(result)
    
    def _convert_blockquotes(self, text: str) -> str:
        """Convert blockquotes to HTML."""
        lines = text.split('\n')
        result = []
        in_blockquote = False
        blockquote_content = []
        
        for line in lines:
            quote_match = self.patterns['blockquote'].match(line)
            if quote_match:
                if not in_blockquote:
                    in_blockquote = True
                blockquote_content.append(quote_match.group(1))
            else:
                if in_blockquote:
                    result.append(f'<blockquote><p>{" ".join(blockquote_content)}</p></blockquote>')
                    blockquote_content = []
                    in_blockquote = False
                result.append(line)
        
        # Close any open blockquote
        if in_blockquote:
            result.append(f'<blockquote><p>{" ".join(blockquote_content)}</p></blockquote>')
        
        return '\n'.join(result)
    
    def _convert_links(self, text: str) -> str:
        """Convert markdown links to HTML."""
        # Markdown links [text](url)
        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2)
            if self.is_email_format:
                return f'<a style="color: #3182ce; text-decoration: none;" href="{url}" target="_blank">{link_text}</a>'
            else:
                return f'<a href="{url}" target="_blank">{link_text}</a>'
        
        text = self.patterns['link'].sub(replace_link, text)
        
        # Auto-links for URLs (but avoid URLs already in HTML tags)
        def replace_auto_link(match):
            url = match.group(0)
            # Check if this URL is already inside an HTML tag
            start_pos = match.start()
            # Look backward for unclosed < tag
            text_before = text[:start_pos]
            last_open = text_before.rfind('<')
            last_close = text_before.rfind('>')
            
            # If we're inside an HTML tag, don't auto-link
            if last_open > last_close:
                return url
                
            if self.is_email_format:
                return f'<a style="color: #3182ce; text-decoration: none;" href="{url}" target="_blank">{url}</a>'
            else:
                return f'<a href="{url}" target="_blank">{url}</a>'
        
        text = self.patterns['auto_link'].sub(replace_auto_link, text)
        
        return text
    
    def _convert_text_formatting(self, text: str) -> str:
        """Convert text formatting (bold, italic, etc.)."""
        # Order matters: do bold before italic to handle ***text***
        text = self.patterns['bold'].sub(r'<strong>\1</strong>', text)
        text = self.patterns['italic'].sub(r'<em>\1</em>', text)
        text = self.patterns['code_inline'].sub(r'<code>\1</code>', text)
        text = self.patterns['strikethrough'].sub(r'<del>\1</del>', text)
        return text
    
    def _convert_line_breaks(self, text: str) -> str:
        """Convert line breaks to HTML."""
        # Convert double line breaks to paragraph breaks
        paragraphs = self.patterns['line_break'].split(text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # Convert single line breaks within paragraphs to <br>
        formatted_paragraphs = []
        for paragraph in paragraphs:
            # Check if this is already HTML content (lists, headers, blockquotes, etc.)
            is_html_element = (
                paragraph.startswith('<') or 
                paragraph.startswith('#') or 
                paragraph.startswith('- ') or 
                paragraph.startswith('* ') or 
                paragraph.startswith('> ') or
                '<ul' in paragraph or '<ol' in paragraph or 
                '<h1' in paragraph or '<h2' in paragraph or '<h3' in paragraph or '<h4' in paragraph or
                '<blockquote' in paragraph or '<pre' in paragraph
            )
            
            if is_html_element:
                formatted_paragraphs.append(paragraph)
            else:
                # For plain text, wrap in paragraphs and handle line breaks
                if paragraph:
                    # Add <br> for single line breaks within regular text
                    formatted = self.patterns['single_break'].sub('<br>', paragraph)
                    formatted = f'<p>{formatted}</p>'
                    formatted_paragraphs.append(formatted)
        
        return '\n\n'.join(formatted_paragraphs)
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML characters in text."""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#x27;'))
    
    def _apply_email_styles(self, html: str) -> str:
        """Apply comprehensive inline styles for email compatibility."""
        # Text formatting
        html = html.replace('<strong>', '<strong style="color: #1a202c; font-weight: 600;">')
        html = html.replace('<em>', '<em style="font-style: italic; color: #4a5568;">')
        
        # Headers
        html = html.replace('<h1>', '<h1 style="color: #1a202c; font-size: 24px; font-weight: 600; margin: 16px 0 8px 0; line-height: 1.3;">')
        html = html.replace('<h2>', '<h2 style="color: #1a202c; font-size: 20px; font-weight: 600; margin: 16px 0 8px 0; line-height: 1.3;">')
        html = html.replace('<h3>', '<h3 style="color: #1a202c; font-size: 18px; font-weight: 600; margin: 16px 0 8px 0; line-height: 1.3;">')
        html = html.replace('<h4>', '<h4 style="color: #1a202c; font-size: 16px; font-weight: 600; margin: 16px 0 8px 0; line-height: 1.3;">')
        
        # Paragraphs
        html = html.replace('<p>', '<p style="margin: 8px 0; line-height: 1.6; color: #2d3748;">')
        
        # Lists
        html = html.replace('<ul>', '<ul style="margin: 12px 0; padding-left: 24px; color: #2d3748;">')
        html = html.replace('<ol>', '<ol style="margin: 12px 0; padding-left: 24px; color: #2d3748;">')
        html = html.replace('<li>', '<li style="margin: 4px 0; line-height: 1.5;">')
        
        # Code
        html = html.replace('<code>', '<code style="background-color: #f7fafc; color: #3182ce; padding: 2px 6px; border-radius: 4px; font-family: Monaco, Menlo, monospace; font-size: 14px; border: 1px solid #e2e8f0;">')
        html = html.replace('<pre>', '<pre style="background-color: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin: 16px 0; overflow-x: auto; font-family: Monaco, Menlo, monospace; font-size: 14px; line-height: 1.4;">')
        
        # Blockquotes
        html = html.replace('<blockquote>', '<blockquote style="border-left: 4px solid #3182ce; background-color: #f7fafc; margin: 16px 0; padding: 12px 16px; border-radius: 0 6px 6px 0;">')
        
        # Horizontal rules
        html = html.replace('<hr>', '<hr style="border: none; height: 1px; background-color: #e2e8f0; margin: 24px 0;">')
        
        return html


# Global converter instance
_converter = MarkdownToHtmlConverter()

def markdown_to_html(text: str) -> str:
    """Convert markdown text to HTML. Main function to use."""
    return _converter.convert(text)

def format_ai_response(text: str) -> str:
    """Format AI response text for web display."""
    if not text:
        return ""
    
    # Convert markdown to HTML
    html = markdown_to_html(text)
    
    # Add some basic styling classes for better presentation
    html = html.replace('<blockquote>', '<blockquote class="ai-quote">')
    html = html.replace('<code>', '<code class="ai-code">')
    html = html.replace('<pre><code', '<pre class="ai-code-block"><code')
    
    return html

def format_ai_response_for_email(text: str) -> str:
    """Format AI response text for email display with inline styles."""
    if not text:
        return ""
    
    # Create email-specific converter
    email_converter = MarkdownToHtmlConverter(is_email_format=True)
    html = email_converter.convert(text)
    
    # The email converter already handles all inline styling automatically
    
    # Wrap in email-friendly HTML structure
    email_html = f'''
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #ffffff;">
        {html}
    </div>
    '''
    
    return email_html.strip()