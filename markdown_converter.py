"""
Конвертер Markdown → Telegram HTML

Преобразует стандартный Markdown (от Gemini API) в HTML,
поддерживаемый Telegram Bot API.
"""

import re


def md_to_telegram_html(text: str) -> str:
    """
    Конвертирует Markdown-текст в Telegram-совместимый HTML.
    
    Поддерживает:
    - **bold** → <b>bold</b>
    - *italic* → <i>italic</i>
    - `code` → <code>code</code>
    - ```code block``` → <pre>code block</pre>
    - # Заголовки → <b>Заголовки</b>
    - [text](url) → <a href="url">text</a>
    - ~~strikethrough~~ → <s>strikethrough</s>
    """
    if not text:
        return text
    
    # Шаг 1: Экранируем HTML-спецсимволы
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Шаг 2: Блоки кода (``` ... ```) — обрабатываем первыми
    # Убираем необязательное имя языка после ```
    text = re.sub(
        r'```(?:\w+)?\n?(.*?)```',
        r'<pre>\1</pre>',
        text,
        flags=re.DOTALL
    )
    
    # Шаг 3: Инлайн-код (` ... `)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    
    # Шаг 4: Жирный текст (**text** или __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    
    # Шаг 5: Курсив (*text* или _text_)
    # Не ловим одиночные * в середине текста
    text = re.sub(r'(?<!\w)\*([^*]+?)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_([^_]+?)_(?!\w)', r'<i>\1</i>', text)
    
    # Шаг 6: Зачеркнутый (~~text~~)
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
    
    # Шаг 7: Ссылки [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    # Шаг 8: Заголовки (# Header) → жирный текст
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    return text
