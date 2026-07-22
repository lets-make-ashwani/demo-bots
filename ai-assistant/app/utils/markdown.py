import re
import html

def markdown_to_html(text: str) -> str:
    """
    Converts standard Markdown text to Telegram-compatible HTML.
    Safely escapes raw html characters and converts markdown formats to HTML tags.
    """
    if not text:
        return ""

    # Split text into code blocks, inline code, and regular text to avoid
    # parsing markdown formatting inside code blocks.
    pattern = r"(```[\s\S]*?```|`[^`\n]*?`)"
    parts = re.split(pattern, text)
    
    for i in range(len(parts)):
        part = parts[i]
        if part.startswith("```") and part.endswith("```"):
            # Extract language and content
            raw_content = part[3:-3]
            # Split language from first line if specified
            lines = raw_content.split("\n", 1)
            lang = ""
            code_content = raw_content
            if len(lines) > 1 and lines[0].strip() and not any(c in lines[0] for c in " \t()"):
                lang = lines[0].strip()
                code_content = lines[1]
            
            escaped_code = html.escape(code_content)
            # Remove leading/trailing newlines
            escaped_code = escaped_code.strip("\n")
            
            if lang:
                parts[i] = f'<pre><code class="language-{lang}">{escaped_code}</code></pre>'
            else:
                parts[i] = f'<pre><code>{escaped_code}</code></pre>'
                
        elif part.startswith("`") and part.endswith("`"):
            code_content = part[1:-1]
            escaped_code = html.escape(code_content)
            parts[i] = f'<code>{escaped_code}</code>'
            
        else:
            # Escape HTML characters first
            escaped = html.escape(part)
            
            # Bold: **text** or __text__
            escaped = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", escaped)
            escaped = re.sub(r"__(.*?)__", r"<b>\1</b>", escaped)
            
            # Italic: *text* or _text_ (excluding inside tags like <b> or <i>)
            # We match *text* only if it has non-whitespace characters inside
            escaped = re.sub(r"\*(?!\s)(.*?)(?<!\s)\*", r"<i>\1</i>", escaped)
            escaped = re.sub(r"_(?!\s)(.*?)(?<!\s)_", r"<i>\1</i>", escaped)
            
            # Strikethrough: ~~text~~
            escaped = re.sub(r"~~(.*?)~~", r"<s>\1</s>", escaped)
            
            # Links: [text](url)
            escaped = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', escaped)
            
            parts[i] = escaped
            
    return "".join(parts)
