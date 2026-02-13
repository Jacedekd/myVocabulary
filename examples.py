"""
Примеры работы с базой данных и API

Этот файл показывает как можно расширить функционал бота
"""

from database import Database
import google.generativeai as genai


# Пример 1: Работа с базой данных напрямую
def example_database():
    """Примеры работы с БД"""
    db = Database()
    
    # Добавить слово
    word_id = db.add_word(
        user_id=123456789,
        word="синтезировать",
        definition="Объединять разрозненные элементы в единое целое",
        context="Прочитал в статье про AI"
    )
    print(f"Добавлено слово с ID: {word_id}")
    
    # Получить все слова пользователя
    words = db.get_user_words(user_id=123456789, limit=10)
    print(f"Найдено слов: {len(words)}")
    
    # Поиск слов
    results = db.search_words(user_id=123456789, query="синтез")
    print(f"Результаты поиска: {results}")
    
    # Статистика
    stats = db.get_user_stats(user_id=123456789)
    print(f"Статистика: {stats}")


# Пример 2: Пакетное добавление слов
def add_multiple_words(user_id: int, words_list: list):
    """
    Добавить несколько слов за раз
    
    Args:
        user_id: ID пользователя
        words_list: Список слов для добавления
    """
    db = Database()
    
    for word in words_list:
        # Получаем определение через Gemini
        prompt = f"Объясни слово '{word}' кратко и понятно"
        # response = model.generate_content(prompt)
        # definition = response.text
        
        # Для примера просто добавим
        db.add_word(user_id, word, f"Определение слова {word}")
        print(f"✅ Добавлено: {word}")


# Пример 3: Экспорт словаря в текстовый файл
def export_to_txt(user_id: int, filename: str = "my_vocabulary.txt"):
    """Экспортировать словарь в текстовый файл"""
    db = Database()
    words = db.get_user_words(user_id)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("МОЙ СЛОВАРЬ\n")
        f.write("=" * 50 + "\n\n")
        
        for idx, word_data in enumerate(words, 1):
            f.write(f"{idx}. {word_data['word'].upper()}\n")
            f.write(f"   {word_data['definition']}\n")
            f.write(f"   Добавлено: {word_data['created_at']}\n\n")
    
    print(f"✅ Экспортировано {len(words)} слов в {filename}")


# Пример 4: Продвинутая статистика
def advanced_stats(user_id: int):
    """Получить продвинутую статистику"""
    db = Database()
    words = db.get_user_words(user_id)
    
    stats = {
        'total_words': len(words),
        'average_definition_length': sum(len(w['definition']) for w in words) / len(words) if words else 0,
        'longest_word': max(words, key=lambda x: len(x['word']))['word'] if words else None,
        'shortest_word': min(words, key=lambda x: len(x['word']))['word'] if words else None,
    }
    
    return stats


# Пример 5: Квиз-система
def generate_quiz(user_id: int, num_questions: int = 5):
    """
    Сгенерировать квиз из сохраненных слов
    
    Returns:
        Список вопросов с вариантами ответов
    """
    import random
    db = Database()
    
    all_words = db.get_user_words(user_id)
    if len(all_words) < 4:
        return None  # Недостаточно слов для квиза
    
    quiz_words = random.sample(all_words, min(num_questions, len(all_words)))
    quiz = []
    
    for word_data in quiz_words:
        correct_word = word_data['word']
        definition = word_data['definition']
        
        # Берем 3 случайных других слова как неправильные варианты
        other_words = [w['word'] for w in all_words if w['word'] != correct_word]
        wrong_answers = random.sample(other_words, min(3, len(other_words)))
        
        # Собираем все варианты и перемешиваем
        options = [correct_word] + wrong_answers
        random.shuffle(options)
        
        quiz.append({
            'definition': definition,
            'options': options,
            'correct_answer': correct_word
        })
    
    return quiz


# Пример 6: Интервальное повторение (Spaced Repetition)
def get_words_for_review(user_id: int):
    """
    Получить слова для повторения по системе интервального повторения
    
    Логика:
    - Новые слова (< 1 дня) - повторять часто
    - Изученные слова (1-7 дней) - повторять реже
    - Старые слова (> 7 дней) - периодическая проверка
    """
    db = Database()
    
    # Слова, которые давно не повторялись (больше недели)
    old_words = db.get_words_to_review(user_id, days=7)
    
    # Можно добавить больше логики:
    # - Слова с высоким приоритетом
    # - Слова, которые часто забывают
    # - и т.д.
    
    return old_words


# Пример 7: Интеграция с другими источниками
def import_from_file(user_id: int, filepath: str):
    """
    Импортировать слова из текстового файла
    
    Формат файла:
    слово1
    слово2
    слово3
    """
    db = Database()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        words = [line.strip() for line in f if line.strip()]
    
    print(f"Импортируем {len(words)} слов...")
    
    for word in words:
        # Здесь можно получить определение через Gemini
        definition = f"Определение слова {word}"  # Placeholder
        db.add_word(user_id, word, definition)
    
    print("✅ Импорт завершен!")


if __name__ == "__main__":
    # Запуск примеров
    print("Примеры работы с API")
    print("=" * 50)
    
    # Раскомментируй нужный пример:
    # example_database()
    # add_multiple_words(123456789, ["контекст", "синтез", "анализ"])
    # export_to_txt(123456789)
    # print(advanced_stats(123456789))
    # print(generate_quiz(123456789))
