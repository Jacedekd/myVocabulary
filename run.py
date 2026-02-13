#!/usr/bin/env python3
"""
Скрипт запуска бота с проверками
"""

import sys
import os

def check_python_version():
    """Проверка версии Python"""
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        print(f"   Твоя версия: {sys.version}")
        return False
    return True

def check_dependencies():
    """Проверка установленных зависимостей"""
    try:
        import telegram
        import google.generativeai
        import dotenv
        return True
    except ImportError as e:
        print(f"❌ Не установлены зависимости: {e}")
        print("   Запусти: pip install -r requirements.txt")
        return False

def check_env_file():
    """Проверка наличия .env файла"""
    if not os.path.exists('.env'):
        print("❌ Файл .env не найден!")
        print("   1. Скопируй .env.example в .env")
        print("   2. Заполни TELEGRAM_BOT_TOKEN и GEMINI_API_KEY")
        return False
    return True

def main():
    """Основная функция запуска"""
    print("🚀 Запуск Vocabulary Bot...\n")
    
    # Проверки
    checks = [
        ("Проверка версии Python", check_python_version),
        ("Проверка зависимостей", check_dependencies),
        ("Проверка .env файла", check_env_file),
    ]
    
    for check_name, check_func in checks:
        print(f"⏳ {check_name}...", end=" ")
        if check_func():
            print("✅")
        else:
            print("")
            return False
    
    print("\n✨ Все проверки пройдены! Запускаем бота...\n")
    
    # Запуск бота
    from main import main as bot_main
    bot_main()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Бот остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
