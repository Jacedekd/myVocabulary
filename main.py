import os
import logging
import asyncio
import json
from datetime import datetime, time, timezone
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
import google.generativeai as genai
from database import Database
from config import check_environment
from markdown_converter import md_to_telegram_html

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверка переменных окружения
if not check_environment():
    exit(1)

# Инициализация
db = Database(os.getenv('DATABASE_URL'))

# Конфигурация Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я твой персональный словарь с AI-помощником. 

📚 <b>Что я умею:</b>
• Объясняю значения слов с примерами
• Сохраняю слова в твой личный словарь
• Показываю все сохраненные слова
• Отправляю случайные слова для повторения

<b>Как пользоваться:</b>
Просто отправь мне любое слово, и я объясню его значение!

<b>Команды:</b>
/dictionary - Мой словарь
/random - Случайное слово для повторения
/stats - Статистика
/subscribe - Включить умные слова
/unsubscribe - Выключить умные слова
/help - Помощь
"""
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = """
📖 <b>Инструкция по использованию:</b>

1️⃣ Отправь мне слово (например: "синтезировать")
2️⃣ Я дам подробное объяснение
3️⃣ Нажми кнопку "💾 Сохранить" чтобы добавить в словарь

<b>Команды:</b>
/dictionary - Посмотреть все сохраненные слова
/random - Получить случайное слово для повторения
/stats - Твоя статистика
/subscribe - Включить ежедневную рассылку новых слов 🔔
/unsubscribe - Выключить рассылку 🔕
/help - Эта справка

<b>Дополнительно:</b>
• Можешь отправить предложение, и я найду сложные слова
• Все слова сохраняются с датой и контекстом
• Рассылка умных слов приходит каждые 3 часа с 6:00 до 21:00
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def get_word_explanation(word: str) -> tuple[str, str]:
    """Получить объяснение слова от Gemini с нормализацией формы"""
    prompt = f"""Ты - эксперт по русскому языку.
Твоя задача: проанализировать слово или фразу "{word}" и вернуть ответ СТРОГО в формате JSON.

ЗАДАЧИ:
1. Исправь орфографические ошибки, если они есть.
2. Приведи слово или фразу к начальной форме (именительный падеж, единственное число, инфинитив для глаголов). 
   Например: "Владимира Жириновского" -> "Владимир Жириновский", "яблоками" -> "яблоко", "делали" -> "делать".
3. Напиши подробное и интересное объяснение значения.

СТРОГИЕ ПРАВИЛА ФОРМАТИРОВАНИЯ ЭКСПЛАНАЦИИ:
- Используй Markdown (**, *, `).
- Каждый заголовок раздела начинай с эмодзи.
- Пункты отмечай точкой •.
- НЕ пиши приветствий и прощаний.

СТРУКТУРА ОБЪЯСНЕНИЯ:
**📝 Краткое определение:**
...
**🔍 Контекст использования:**
• ...
**💬 Примеры предложений:**
• ...
**🔄 Синонимы:**
• ...
**🧠 Происхождение слова:**
...
**💡 Интересный факт:**
...

ВЕРНИ ОТВЕТ ТОЛЬКО В JSON:
{{
    "normalized_word": "Исправленное слово в начальной форме (с заглавной буквы если это имя собственное)",
    "explanation": "Текст объяснения в формате Markdown"
}}"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            text = response.text
            
            # Очистка от markdown блоков json
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "")
            elif text.startswith("```"):
                text = text.replace("```", "")
                
            data = json.loads(text.strip())
            norm_word = data.get('normalized_word', word)
            explanation_html = md_to_telegram_html(data.get('explanation', "Ошибка получения объяснения"))
            
            return norm_word, explanation_html
            
        except Exception as e:
            error_msg = str(e)
            if ("429" in error_msg or "Resource exhausted" in error_msg) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                logger.warning(f"⚠️ Gemini API 429, ждем {wait_time}с...")
                await asyncio.sleep(wait_time)
                continue
            
            logger.error(f"Ошибка Gemini API: {e}")
            return word, "⚠️ Произошла ошибка при получении объяснения. Попробуй через минуту."


async def get_smart_word_suggestion(existing_words: list) -> tuple[str, str] | None:
    """Генерация умного слова на основе контекста"""
    context_text = ", ".join([w['word'] for w in existing_words]) if existing_words else "эмпатия, амбивалентность, когнитивный"
    
    prompt = f"""
    Ты - эксперт по русскому языку. Пользователь изучает сложные, "умные" слова.
    
    Его текущий словарный запас включает: {context_text}.
    
    Предложи 1 НОВОЕ слово, которого нет в этом списке, но которое подходит по стилю (интеллектуальное, книжное, научное или философское).
    
    Ответ верни СТРОГО в формате JSON:
    {{
        "word": "СЛОВО",
        "explanation": "Текст объяснения с форматированием Markdown (жирный, курсив). Включи определение, синонимы, контекст использования и интересный факт. Используй эмодзи."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text
        # Очистка от markdown блоков json, если они есть
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "")
        elif text.startswith("```"):
            text = text.replace("```", "")
            
        data = json.loads(text.strip())
        return data['word'], md_to_telegram_html(data['explanation'])
    except Exception as e:
        logger.error(f"Ошибка генерации умного слова: {e}")
        return None


async def daily_word_job(context: ContextTypes.DEFAULT_TYPE):
    """Задача рассылки ежедневных слов"""
    users = db.get_subscribed_users()
    
    for user_id in users:
        try:
            # Берем последние 20 слов для контекста
            words = db.get_user_words(user_id, limit=20)
            
            suggestion = await get_smart_word_suggestion(words)
            if not suggestion:
                continue
                
            word, explanation = suggestion
            
            # Сохраняем в user_data (если используется persistence, или в памяти)
            if not context.application.user_data.get(user_id):
                context.application.user_data[user_id] = {}
            
            context.application.user_data[user_id]['last_word'] = word
            context.application.user_data[user_id]['last_explanation'] = explanation
            
            # Кнопка сохранения
            keyboard = [[InlineKeyboardButton("💾 Сохранить в словарь", callback_data="save_word")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔔 <b>Слово дня</b>\n\n📖 <b>{word.upper()}</b>\n\n{explanation}",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            # Небольшая пауза между пользователями, чтобы не спамить API слишком быстро
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Ошибка отправки слова юзеру {user_id}: {e}")
            # Если бот заблокирован пользователем, можно отписать его
            if "Forbidden" in str(e):
                db.subscribe_user(user_id, False)


async def post_init(application: Application):
    """Установка команд бота при запуске"""
    await application.bot.set_my_commands([
        ("dictionary", "📚 Мой словарь"),
        ("random", "🎲 Случайное слово"),
        ("stats", "📊 Статистика"),
        ("subscribe", "🔔 Включить умные слова"),
        ("unsubscribe", "🔕 Выключить умные слова"),
        ("help", "ℹ️ Помощь"),
        ("start", "👋 Перезапустить бота")
    ])


async def handle_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка слова от пользователя"""
    user_id = update.effective_user.id
    word = update.message.text.strip()
    
    # Проверяем, что это действительно слово (не длинный текст)
    if len(word.split()) > 3:
        await update.message.reply_text(
            "🤔 Это похоже на предложение, роднулька. Отправь одно слово или короткую фразу."
        )
        return
    
    # Гарантируем, что пользователь есть в базе (важно для Postgres)
    db.add_user(user_id, update.effective_user.username, update.effective_user.first_name)
    
    # Показываем индикатор печати
    await update.message.chat.send_action("typing")
    
    # Получаем объяснение и нормализованное слово
    normalized_word, explanation = await get_word_explanation(word)
    
    # Сохраняем последнее слово в контекст для возможности сохранения
    # Используем нормализованное слово, чтобы в базу попало "яблоко", а не "яблоками"
    context.user_data['last_word'] = normalized_word
    context.user_data['last_explanation'] = explanation
    
    # Создаем клавиатуру с кнопкой сохранения
    keyboard = [
        [
            InlineKeyboardButton("💾 Сохранить в словарь", callback_data="save_word")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📖 <b>{normalized_word.upper()}</b>\n\n{explanation}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "save_word":
        # ОБНОВЛЯЕМ КНОПКУ МГНОВЕННО (Оптимистичный UI)
        new_keyboard = [[InlineKeyboardButton("✅ Сохранено", callback_data="noop")]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
        await query.answer("Слово сохранено!")
        
        # Сохранение слова в базу в фоновом режиме (уже не блокируем пользователя)
        word = context.user_data.get('last_word')
        explanation = context.user_data.get('last_explanation')
        
        if word and explanation:
            # db.add_word сам гарантирует наличие пользователя (add_user внутри не нужен)
            db.add_word(user_id, word, explanation)
        else:
            logger.warning(f"Failed optimistic save for user {user_id}: data missing")
            
    elif data == "noop":
         # Пустая заглушка для уже нажатых кнопок
         await query.answer()
    
    elif data == "show_dictionary":
        # Показать словарь (с первой страницы)
        await show_dictionary(update, context, page=0)

    elif data == "random_word":
        # Случайное слово
        await random_word_command(update, context)

    elif data == "show_stats":
        # Статистика
        await stats_command(update, context)
        
    elif data.startswith("dict_page_"):
        # Пагинация словаря
        page = int(data.split("_")[2])
        await show_dictionary(update, context, page=page)
        
    elif data.startswith("view_word_"):
        # Просмотр слова из словаря
        word_id = int(data.split("_")[2])
        word_data = db.get_word_by_id(word_id)
        
        if word_data:
            # Отправляем НОВЫМ сообщением, чтобы не терять список
            # Кнопка "Удалить" вместо "Сохранить"
            keyboard = [[InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_word_{word_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📖 <b>{word_data['word'].upper()}</b>\n\n{word_data['definition']}",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        else:
            await query.answer("Слово не найдено", show_alert=True)

    elif data.startswith("delete_word_"):
        # Удаление слова
        word_id = int(data.split("_")[2])
        if db.delete_word(word_id, user_id):
            await query.answer("Слово удалено")
            await query.delete_message()
        else:
            await query.answer("Ошибка удаления", show_alert=True)


async def show_dictionary(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показать словарь пользователя с пагинацией"""
    user_id = update.effective_user.id
    PER_PAGE = 5
    
    # Получаем ВСЕ данные одним махом (оптимизация)
    dict_data = db.get_dictionary_data(user_id, limit=PER_PAGE, offset=page * PER_PAGE)
    total_words = dict_data['total_words']
    words = dict_data['words']
    
    if not words and page == 0:
        text = "📚 Твой словарь пока пуст.\nОтправь мне слово, чтобы начать!"
        reply_markup = None
    else:
        text = f"📚 <b>Твой словарь (всего {total_words}):</b>\n\nВыберите слово, чтобы прочитать его значение:"
        
        keyboard = []
        # Кнопки со словами
        for word_data in words:
            keyboard.append([
                InlineKeyboardButton(f"📖 {word_data['word']}", callback_data=f"view_word_{word_data['id']}")
            ])
            
        # Пагинация
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"dict_page_{page-1}"))
            
        total_pages = (total_words + PER_PAGE - 1) // PER_PAGE
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        
        if (page + 1) * PER_PAGE < total_words:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"dict_page_{page+1}"))
            
        if nav_buttons:
            keyboard.append(nav_buttons)
            
        # Доп. кнопки
        keyboard.append([
            InlineKeyboardButton("🎲 Случайное слово", callback_data="random_word"),
            InlineKeyboardButton("📊 Статистика", callback_data="show_stats")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправка или редактирование сообщения
    if update.callback_query and update.callback_query.message:
        # Если это навигация внутри словаря (страницы), редактируем
        # Но если это первый вход через '/dictionary', то это message, а не callback_query (обычно)
        # Если вызов через callback (навигация), редактируем
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        # Если вызов через команду, отправляем новое
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )


async def dictionary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для показа словаря"""
    await show_dictionary(update, context)


async def random_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить случайное слово для повторения"""
    user_id = update.effective_user.id
    word_data = db.get_random_word(user_id)
    
    if not word_data:
        await update.message.reply_text(
            "📚 Твой словарь пуст. Сначала добавь несколько слов!"
        )
        return
    
    text = f"""
🎲 Случайное слово для повторения:

{word_data['word'].upper()}

{word_data['definition']}

Добавлено: {word_data['created_at']}
"""
    
    keyboard = [[InlineKeyboardButton("🎲 Еще слово", callback_data="random_word")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику пользователя"""
    user_id = update.effective_user.id
    stats = db.get_user_stats(user_id)
    
    text = f"""
📊 Твоя статистика:

📚 Всего слов: {stats['total_words']}
📅 Первое слово: {stats['first_word_date'] or 'нет данных'}
🆕 Последнее слово: {stats['last_word_date'] or 'нет данных'}

Продолжай в том же духе! 🚀
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписаться на ежедневные слова"""
    user_id = update.effective_user.id
    db.subscribe_user(user_id, True)
    await update.message.reply_text(
        "✅ <b>Подписка включена!</b>\n\n"
        "Теперь я буду присылать тебе новые умные слова каждые 3 часа с 6:00 до 21:00.\n"
        "Слова будут подбираться на основе твоего словаря.",
        parse_mode=ParseMode.HTML
    )

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отписаться от ежедневных слов"""
    user_id = update.effective_user.id
    db.subscribe_user(user_id, False)
    await update.message.reply_text(
        "🔕 <b>Подписка выключена.</b>\n"
        "Больше не буду беспокоить тебя автоматическими сообщениями.",
        parse_mode=ParseMode.HTML
    )


def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("dictionary", dictionary_command))
    application.add_handler(CommandHandler("random", random_word_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    
    # Рекуррентные задачи (ежедневные слова)
    # Время UTC (UTC+6 - 6 часов = UTC)
    # 6:00 UTC+6 = 0:00 UTC
    times = [
        time(hour=0, tzinfo=timezone.utc),  # 6:00
        time(hour=3, tzinfo=timezone.utc),  # 9:00
        time(hour=6, tzinfo=timezone.utc),  # 12:00
        time(hour=9, tzinfo=timezone.utc),  # 15:00
        time(hour=12, tzinfo=timezone.utc), # 18:00
        time(hour=15, tzinfo=timezone.utc), # 21:00
    ]
    
    for t in times:
        application.job_queue.run_daily(daily_word_job, time=t)

    # Обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик текстовых сообщений (слов)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_word
    ))
    
    # Запускаем бота
    if os.getenv('RENDER'):
        # Настройки для Render (Webhooks + Health Check)
        port = int(os.getenv('PORT', 10000))
        url = os.getenv('RENDER_EXTERNAL_URL')
        
        async def health_check(request):
            """Обработчик для пинга: будит и бота, и базу данных"""
            try:
                # Делаем фиктивный запрос к базе, чтобы Supabase не уснул
                db.init_db() 
                return web.Response(text="OK - Bot and DB are alive", content_type="text/plain")
            except Exception as e:
                logger.error(f"Health check DB error: {e}")
                return web.Response(text="OK - Bot alive, DB error", content_type="text/plain")

        async def run_custom_webhook():
            """Запуск веб-сервера вручную для поддержки кастомных путей"""
            await application.initialize()
            await application.start()
            
            # Создаем aiohttp приложение
            app = web.Application()
            app.router.add_get("/", health_check)
            
            # Обработчик вебхука Телеграма
            async def telegram_webhook(request):
                update = Update.de_json(await request.json(), application.bot)
                await application.process_update(update)
                return web.Response()

            app.router.add_post(f"/{TELEGRAM_TOKEN}", telegram_webhook)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", port)
            
            logger.info(f"🚀 Запуск кастомного веб-сервера на порту {port}")
            logger.info(f"🔗 Health check доступен по: {url}/")
            
            await site.start()
            
            # Держим процесс запущенным
            try:
                # Бесконечный цикл ожидания
                while True:
                    await asyncio.sleep(3600)
            finally:
                await application.stop()
                await application.shutdown()

        # Запускаем в текущем цикле событий
        asyncio.get_event_loop().run_until_complete(run_custom_webhook())
    else:
        # Настройки для локальной разработки (Polling)
        logger.info("🤖 Запуск в режиме Polling")
        application.run_polling(allowed_updates=Update.ALL_TYPES)



if __name__ == '__main__':
    main()
