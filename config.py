import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Проверка наличия обязательных переменных
def check_environment():
    """Проверить наличие всех необходимых переменных окружения"""
    required_vars = ['TELEGRAM_BOT_TOKEN', 'GEMINI_API_KEY']
    
    # Если мы на Render, нужен еще URL для вебхука
    if os.getenv('RENDER'):
        required_vars.append('RENDER_EXTERNAL_URL')
    
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Отсутствуют обязательные переменные окружения:")
        for var in missing_vars:
            print(f"   - {var}")
        
        if 'RENDER_EXTERNAL_URL' in missing_vars:
            print("\n💡 Подсказка для Render: добавь переменную RENDER_EXTERNAL_URL с адресом твоего сервиса (например, https://bot-name.onrender.com)")
            
        print("\n💡 Создай файл .env на основе .env.example и заполни его!")
        return False
    
    return True

