import sqlite3
import random
from datetime import datetime
from typing import List, Dict, Optional


class Database:
    """Класс для работы с базой данных (SQLite или PostgreSQL)"""
    
    def __init__(self, db_url: str = None):
        """
        Инициализация базы данных
        
        Args:
            db_url: Путь к файлу SQLite или строка подключения PostgreSQL (URL)
        """
        self.db_url = db_url or "vocabulary.db"
        self.is_postgres = self.db_url.startswith("postgres")
        
        if self.is_postgres:
            import psycopg2
            from psycopg2 import pool
            from psycopg2.extras import RealDictRow
            self._connection_factory = psycopg2.connect
            self._row_factory_arg = RealDictRow
            # Используем ThreadedConnectionPool для безопасности (мин 2, макс 20)
            self.pool = pool.ThreadedConnectionPool(2, 20, self.db_url)
        else:
            import sqlite3
            self._connection_factory = sqlite3.connect
            self._row_factory_arg = sqlite3.Row
            self.pool = None
            
        self.init_db()
    
    def get_connection(self):
        """Получить соединение с БД из пула (если есть)"""
        if self.is_postgres and self.pool:
            return self.pool.getconn()
            
        conn = self._connection_factory(self.db_url)
        if not self.is_postgres:
            conn.row_factory = self._row_factory_arg
        return conn
    
    def release_connection(self, conn):
        """Вернуть соединение в пул"""
        if self.is_postgres and self.pool:
            self.pool.putconn(conn)
        else:
            conn.close()
    
    def get_cursor(self, conn):
        """Получить курсор"""
        if self.is_postgres:
            from psycopg2.extras import RealDictCursor
            return conn.cursor(cursor_factory=RealDictCursor)
        return conn.cursor()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            
            # Таблица пользователей
            user_table_sql = """
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    is_subscribed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """ if self.is_postgres else """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    is_subscribed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            cursor.execute(user_table_sql)
            
            # Таблица слов
            word_table_sql = """
                CREATE TABLE IF NOT EXISTS words (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    word TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_reviewed TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """ if self.is_postgres else """
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
            """
            cursor.execute(word_table_sql)
            
            # Индексы
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_words ON words(user_id, created_at DESC)")
            
            # Миграция: добавляем колонку подписки, если её нет (для SQLite, в Postgres создали сразу)
            if not self.is_postgres:
                try:
                    cursor.execute("ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT 0")
                except Exception:
                    pass
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None):
        """Добавить пользователя"""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            if self.is_postgres:
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                """, (user_id, username, first_name))
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, username, first_name)
                    VALUES (?, ?, ?)
                """, (user_id, username, first_name))
            conn.commit()
        finally:
            self.release_connection(conn)

    def subscribe_user(self, user_id: int, subscribed: bool = True):
        """Включить/выключить подписку на ежедневные слова"""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            placeholder = "%s" if self.is_postgres else "?"
            cursor.execute(f"""
                UPDATE users 
                SET is_subscribed = {placeholder}
                WHERE user_id = {placeholder}
            """, (subscribed, user_id))
            conn.commit()
        finally:
            self.release_connection(conn)
        
    def get_subscribed_users(self) -> List[int]:
        """Получить список ID подписанных пользователей"""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            if self.is_postgres:
                cursor.execute("SELECT user_id FROM users WHERE is_subscribed = TRUE")
            else:
                cursor.execute("SELECT user_id FROM users WHERE is_subscribed = 1")
            return [row['user_id'] for row in cursor.fetchall()]
        finally:
            self.release_connection(conn)
    
    def add_word(self, user_id: int, word: str, definition: str, context: str = None) -> int:
        """
        Добавить слово в словарь
        """
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            # FAIL-SAFE: Гарантируем наличие пользователя перед добавлением слова
            if self.is_postgres:
                cursor.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
            else:
                cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
                
            p = "%s" if self.is_postgres else "?"
            cursor.execute(f"SELECT id FROM words WHERE user_id = {p} AND LOWER(word) = LOWER({p})", (user_id, word))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute(f"UPDATE words SET definition = {p}, context = {p}, created_at = CURRENT_TIMESTAMP WHERE id = {p}", 
                             (definition, context, existing['id']))
                word_id = existing['id']
            else:
                if self.is_postgres:
                    cursor.execute("INSERT INTO words (user_id, word, definition, context) VALUES (%s, %s, %s, %s) RETURNING id",
                                 (user_id, word, definition, context))
                    word_id = cursor.fetchone()['id']
                else:
                    cursor.execute("INSERT INTO words (user_id, word, definition, context) VALUES (?, ?, ?, ?)",
                                 (user_id, word, definition, context))
                    word_id = cursor.lastrowid
            conn.commit()
            return word_id
        finally:
            self.release_connection(conn)
    
    def get_user_words(self, user_id: int, limit: int = None, offset: int = 0) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            if self.is_postgres:
                query = f"SELECT id, word, definition, context, created_at, last_reviewed FROM words WHERE user_id = {p} ORDER BY created_at DESC"
            else:
                query = f"SELECT id, word, definition, context, datetime(created_at, 'localtime') as created_at, last_reviewed FROM words WHERE user_id = {p} ORDER BY created_at DESC"
            
            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"
            
            cursor.execute(query, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            self.release_connection(conn)

    def get_word_by_id(self, word_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            if self.is_postgres:
                sql = f"SELECT id, word, definition, context, created_at, last_reviewed FROM words WHERE id = {p}"
            else:
                sql = f"SELECT id, word, definition, context, datetime(created_at, 'localtime') as created_at, last_reviewed FROM words WHERE id = {p}"
            cursor.execute(sql, (word_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self.release_connection(conn)

    def search_words(self, user_id: int, query: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            if self.is_postgres:
                sql = f"SELECT id, word, definition, context, created_at FROM words WHERE user_id = {p} AND (word ILIKE {p} OR definition ILIKE {p}) ORDER BY created_at DESC"
                cursor.execute(sql, (user_id, f"%{query}%", f"%{query}%"))
            else:
                sql = f"SELECT id, word, definition, context, datetime(created_at, 'localtime') as created_at FROM words WHERE user_id ? AND (LOWER(word) LIKE LOWER(?) OR LOWER(definition) LIKE LOWER(?)) ORDER BY created_at DESC"
                cursor.execute(sql, (user_id, f"%{query}%", f"%{query}%"))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            self.release_connection(conn)

    def get_random_word(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            if self.is_postgres:
                sql = f"SELECT id, word, definition, context, created_at FROM words WHERE user_id = {p} ORDER BY RANDOM() LIMIT 1"
            else:
                sql = f"SELECT id, word, definition, context, datetime(created_at, 'localtime') as created_at FROM words WHERE user_id = ? ORDER BY RANDOM() LIMIT 1"
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self.release_connection(conn)

    def update_last_reviewed(self, word_id: int):
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            cursor.execute(f"UPDATE words SET last_reviewed = CURRENT_TIMESTAMP WHERE id = {p}", (word_id,))
            conn.commit()
        finally:
            self.release_connection(conn)

    def delete_word(self, word_id: int, user_id: int) -> bool:
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            cursor.execute(f"DELETE FROM words WHERE id = {p} AND user_id = {p}", (word_id, user_id))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        finally:
            self.release_connection(conn)

    def get_user_stats(self, user_id: int) -> Dict:
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            
            if self.is_postgres:
                sql = f"SELECT COUNT(*) as total_words, MIN(created_at) as first_word_date, MAX(created_at) as last_word_date FROM words WHERE user_id = {p}"
            else:
                sql = f"SELECT COUNT(*) as total_words, MIN(datetime(created_at, 'localtime')) as first_word_date, MAX(datetime(created_at, 'localtime')) as last_word_date FROM words WHERE user_id = ?"
                
            cursor.execute(sql, (user_id,))
            return dict(cursor.fetchone())
        finally:
            self.release_connection(conn)

    def get_words_to_review(self, user_id: int, days: int = 7) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            
            if self.is_postgres:
                sql = f"SELECT id, word, definition, context, created_at, last_reviewed FROM words WHERE user_id = {p} AND (last_reviewed IS NULL OR last_reviewed <= CURRENT_TIMESTAMP - INTERVAL '{days} days') ORDER BY RANDOM() LIMIT 10"
                cursor.execute(sql, (user_id,))
            else:
                sql = f"SELECT id, word, definition, context, datetime(created_at, 'localtime') as created_at, last_reviewed FROM words WHERE user_id = ? AND (last_reviewed IS NULL OR julianday('now') - julianday(last_reviewed) >= ?) ORDER BY RANDOM() LIMIT 10"
                cursor.execute(sql, (user_id, days))
                
            return [dict(row) for row in cursor.fetchall()]
        finally:
            self.release_connection(conn)


    def get_dictionary_data(self, user_id: int, limit: int = 5, offset: int = 0) -> Dict:
        """
        Получить все данные для словаря за ОДИН запрос (оптимизация)
        """
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            p = "%s" if self.is_postgres else "?"
            
            # 1. Считаем статистику
            if self.is_postgres:
                sql_stats = f"SELECT COUNT(*) as total_words FROM words WHERE user_id = {p}"
            else:
                sql_stats = f"SELECT COUNT(*) as total_words FROM words WHERE user_id = ?"
            
            cursor.execute(sql_stats, (user_id,))
            total_words = cursor.fetchone()['total_words']
            
            # 2. Получаем слова
            if self.is_postgres:
                sql_words = f"SELECT id, word FROM words WHERE user_id = {p} ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
            else:
                sql_words = f"SELECT id, word FROM words WHERE user_id = ? ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
                
            cursor.execute(sql_words, (user_id,))
            words = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_words': total_words,
                'words': words
            }
        finally:
            self.release_connection(conn)
