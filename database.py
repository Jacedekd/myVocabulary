import sqlite3
import random
from datetime import datetime
from typing import List, Dict, Optional


class Database:
    """Класс для работы с базой данных словаря"""
    
    def __init__(self, db_path: str = "vocabulary.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Получить соединение с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица слов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                definition TEXT NOT NULL,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_reviewed TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_words 
            ON words(user_id, created_at DESC)
        """)
        
        # Миграция: добавляем колонку подписки, если её нет
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None):
        """Добавить пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username, first_name))
        
        conn.commit()
        conn.close()

    def subscribe_user(self, user_id: int, subscribed: bool = True):
        """Включить/выключить подписку на ежедневные слова"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET is_subscribed = ? 
            WHERE user_id = ?
        """, (1 if subscribed else 0, user_id))
        
        conn.commit()
        conn.close()
        
    def get_subscribed_users(self) -> List[int]:
        """Получить список ID подписанных пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM users WHERE is_subscribed = 1")
        users = [row['user_id'] for row in cursor.fetchall()]
        
        conn.close()
        return users
    
    def add_word(self, user_id: int, word: str, definition: str, context: str = None) -> int:
        """
        Добавить слово в словарь
        
        Returns:
            ID добавленного слова
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже такое слово у пользователя
        cursor.execute("""
            SELECT id FROM words 
            WHERE user_id = ? AND LOWER(word) = LOWER(?)
        """, (user_id, word))
        
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующее слово
            cursor.execute("""
                UPDATE words 
                SET definition = ?, context = ?, created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (definition, context, existing['id']))
            word_id = existing['id']
        else:
            # Добавляем новое слово
            cursor.execute("""
                INSERT INTO words (user_id, word, definition, context)
                VALUES (?, ?, ?, ?)
            """, (user_id, word, definition, context))
            word_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return word_id
    
    def get_user_words(self, user_id: int, limit: int = None, offset: int = 0) -> List[Dict]:
        """
        Получить все слова пользователя
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество слов
            offset: Смещение (для пагинации)
        
        Returns:
            Список словарей со словами
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT id, word, definition, context, 
                   datetime(created_at, 'localtime') as created_at,
                   last_reviewed
            FROM words
            WHERE user_id = ?
            ORDER BY created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        cursor.execute(query, (user_id,))
        words = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return words
    
    def get_word_by_id(self, word_id: int) -> Optional[Dict]:
        """Получить слово по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, word, definition, context,
                   datetime(created_at, 'localtime') as created_at,
                   last_reviewed
            FROM words
            WHERE id = ?
        """, (word_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def search_words(self, user_id: int, query: str) -> List[Dict]:
        """
        Поиск слов по запросу
        
        Args:
            user_id: ID пользователя
            query: Поисковый запрос
        
        Returns:
            Список найденных слов
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, word, definition, context,
                   datetime(created_at, 'localtime') as created_at
            FROM words
            WHERE user_id = ? AND (
                LOWER(word) LIKE LOWER(?) OR
                LOWER(definition) LIKE LOWER(?)
            )
            ORDER BY created_at DESC
        """, (user_id, f"%{query}%", f"%{query}%"))
        
        words = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return words
    
    def get_random_word(self, user_id: int) -> Optional[Dict]:
        """Получить случайное слово пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, word, definition, context,
                   datetime(created_at, 'localtime') as created_at
            FROM words
            WHERE user_id = ?
            ORDER BY RANDOM()
            LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def update_last_reviewed(self, word_id: int):
        """Обновить время последнего повторения"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE words
            SET last_reviewed = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (word_id,))
        
        conn.commit()
        conn.close()
    
    def delete_word(self, word_id: int, user_id: int) -> bool:
        """
        Удалить слово
        
        Returns:
            True если удалено, False если не найдено
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM words
            WHERE id = ? AND user_id = ?
        """, (word_id, user_id))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_user_stats(self, user_id: int) -> Dict:
        """
        Получить статистику пользователя
        
        Returns:
            Словарь со статистикой
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Общее количество слов
        cursor.execute("""
            SELECT COUNT(*) as total_words,
                   MIN(datetime(created_at, 'localtime')) as first_word_date,
                   MAX(datetime(created_at, 'localtime')) as last_word_date
            FROM words
            WHERE user_id = ?
        """, (user_id,))
        
        stats = dict(cursor.fetchone())
        conn.close()
        
        return stats
    
    def get_words_to_review(self, user_id: int, days: int = 7) -> List[Dict]:
        """
        Получить слова, которые давно не повторялись
        
        Args:
            user_id: ID пользователя
            days: Количество дней с последнего повторения
        
        Returns:
            Список слов для повторения
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, word, definition, context,
                   datetime(created_at, 'localtime') as created_at,
                   last_reviewed
            FROM words
            WHERE user_id = ? AND (
                last_reviewed IS NULL OR
                julianday('now') - julianday(last_reviewed) >= ?
            )
            ORDER BY RANDOM()
            LIMIT 10
        """, (user_id, days))
        
        words = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return words


# Если нужно мигрировать на PostgreSQL, используй этот класс:
class PostgresDatabase(Database):
    """
    Версия для PostgreSQL (для продакшена)
    
    Установка: pip install psycopg2-binary
    """
    
    def __init__(self, connection_string: str):
        import psycopg2
        import psycopg2.extras
        
        self.connection_string = connection_string
        self.init_db()
    
    def get_connection(self):
        import psycopg2
        import psycopg2.extras
        
        conn = psycopg2.connect(self.connection_string)
        return conn
    
    # Методы аналогичные, но с синтаксисом PostgreSQL
    # Здесь нужно адаптировать SQL-запросы под PostgreSQL
