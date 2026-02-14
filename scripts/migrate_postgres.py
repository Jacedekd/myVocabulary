import psycopg2
from psycopg2.extras import RealDictCursor
import sys

def migrate(old_url, new_url):
    """
    Миграция данных из старой базы (Render) в новую (Supabase/Neon)
    """
    try:
        print("🔗 Подключение к старой базе (Source)...")
        conn_old = psycopg2.connect(old_url)
        cursor_old = conn_old.cursor(cursor_factory=RealDictCursor)

        print("🔗 Подключение к новой базе (Target)...")
        conn_new = psycopg2.connect(new_url)
        cursor_new = conn_new.cursor()

        # 1. Переносим пользователей
        print("👥 Миграция пользователей...")
        cursor_old.execute("SELECT * FROM users")
        users = cursor_old.fetchall()
        
        for user in users:
            cursor_new.execute(
                "INSERT INTO users (user_id, username, first_name, is_subscribed, created_at) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET "
                "username = EXCLUDED.username, first_name = EXCLUDED.first_name, is_subscribed = EXCLUDED.is_subscribed",
                (user['user_id'], user['username'], user['first_name'], user['is_subscribed'], user['created_at'])
            )
        print(f"✅ Перенесено пользователей: {len(users)}")

        # 2. Переносим слова
        print("📚 Миграция слов...")
        cursor_old.execute("SELECT * FROM words")
        words = cursor_old.fetchall()
        
        for word in words:
            # Проверяем на дубликаты по user_id и word
            cursor_new.execute(
                "INSERT INTO words (user_id, word, definition, context, created_at, last_reviewed) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (word['user_id'], word['word'], word['definition'], word['context'], word['created_at'], word['last_reviewed'])
            )
        print(f"✅ Перенесено слов: {len(words)}")

        conn_new.commit()
        print("\n🎉 МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")

    except Exception as e:
        print(f"\n❌ ОШИБКА МИГРАЦИИ: {e}")
        sys.exit(1)
    finally:
        if 'conn_old' in locals(): conn_old.close()
        if 'conn_new' in locals(): conn_new.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python migrate_postgres.py <OLD_URL> <NEW_URL>")
        sys.exit(1)
    
    migrate(sys.argv[1], sys.argv[2])
