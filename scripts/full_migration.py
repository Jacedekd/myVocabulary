from database import Database
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

def init_and_migrate(old_url, new_url):
    # 1. Инициализируем схему в новой базе
    print("🏗 Инициализация схемы в новой базе...")
    db_new = Database(new_url)
    print("✅ Схема готова.")

    # 2. Запускаем миграцию
    try:
        print("\n🔗 Подключение к старой базе (Source)...")
        conn_old = psycopg2.connect(old_url)
        cursor_old = conn_old.cursor(cursor_factory=RealDictCursor)

        print("🔗 Подключение к новой базе (Target)...")
        conn_new = psycopg2.connect(new_url)
        cursor_new = conn_new.cursor()

        # Переносим пользователей
        print("👥 Перенос пользователей...")
        cursor_old.execute("SELECT * FROM users")
        users = cursor_old.fetchall()
        for u in users:
            cursor_new.execute(
                "INSERT INTO users (user_id, username, first_name, is_subscribed, created_at) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET "
                "username = EXCLUDED.username, first_name = EXCLUDED.first_name, is_subscribed = EXCLUDED.is_subscribed",
                (u['user_id'], u['username'], u['first_name'], u['is_subscribed'], u['created_at'])
            )
        print(f"✅ Успешно: {len(users)}")

        # Переносим слова
        print("📚 Перенос слов...")
        cursor_old.execute("SELECT * FROM words")
        words = cursor_old.fetchall()
        for w in words:
            cursor_new.execute(
                "INSERT INTO words (user_id, word, definition, context, created_at, last_reviewed) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (w['user_id'], w['word'], w['definition'], w['context'], w['created_at'], w['last_reviewed'])
            )
        print(f"✅ Успешно: {len(words)}")

        conn_new.commit()
        print("\n🎉 МИГРАЦИЯ ЗАВЕРШЕНА!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        if 'conn_old' in locals(): conn_old.close()
        if 'conn_new' in locals(): conn_new.close()

if __name__ == "__main__":
    old = "postgresql://myvocabulary_user:u7nOnW6xW58KzFp6sAnS6n43gT8BfGst@dpg-culn5p1opnds73arngog-a.singapore-postgres.render.com/myvocabulary"
    new = "postgresql://postgres.gwwoumwlckqctcvuaggl:huGroj-cuvvy1-cyghuv@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
    init_and_migrate(old, new)
