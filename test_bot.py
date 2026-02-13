"""
Тесты для бота

Запуск: python test_bot.py
"""

import unittest
import os
from database import Database


class TestDatabase(unittest.TestCase):
    """Тесты для базы данных"""
    
    def setUp(self):
        """Создаем тестовую БД перед каждым тестом"""
        self.test_db_path = "test_vocabulary.db"
        self.db = Database(self.test_db_path)
        self.test_user_id = 123456789
    
    def tearDown(self):
        """Удаляем тестовую БД после каждого теста"""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    def test_add_word(self):
        """Тест добавления слова"""
        word_id = self.db.add_word(
            user_id=self.test_user_id,
            word="тест",
            definition="Проверка функциональности"
        )
        self.assertIsNotNone(word_id)
        self.assertGreater(word_id, 0)
    
    def test_get_user_words(self):
        """Тест получения слов пользователя"""
        # Добавляем несколько слов
        self.db.add_word(self.test_user_id, "слово1", "определение1")
        self.db.add_word(self.test_user_id, "слово2", "определение2")
        self.db.add_word(self.test_user_id, "слово3", "определение3")
        
        # Получаем слова
        words = self.db.get_user_words(self.test_user_id)
        
        self.assertEqual(len(words), 3)
        self.assertEqual(words[0]['word'], "слово3")  # Последнее добавленное
    
    def test_search_words(self):
        """Тест поиска слов"""
        # Добавляем слова
        self.db.add_word(self.test_user_id, "синтезировать", "объединять")
        self.db.add_word(self.test_user_id, "анализировать", "разбирать")
        self.db.add_word(self.test_user_id, "контекст", "окружение")
        
        # Ищем слова с "синтез"
        results = self.db.search_words(self.test_user_id, "синтез")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['word'], "синтезировать")
    
    def test_get_random_word(self):
        """Тест получения случайного слова"""
        # Добавляем слово
        self.db.add_word(self.test_user_id, "случайное", "тестовое слово")
        
        # Получаем случайное слово
        word = self.db.get_random_word(self.test_user_id)
        
        self.assertIsNotNone(word)
        self.assertEqual(word['word'], "случайное")
    
    def test_get_user_stats(self):
        """Тест получения статистики"""
        # Добавляем слова
        self.db.add_word(self.test_user_id, "слово1", "определение1")
        self.db.add_word(self.test_user_id, "слово2", "определение2")
        
        # Получаем статистику
        stats = self.db.get_user_stats(self.test_user_id)
        
        self.assertEqual(stats['total_words'], 2)
        self.assertIsNotNone(stats['first_word_date'])
        self.assertIsNotNone(stats['last_word_date'])
    
    def test_delete_word(self):
        """Тест удаления слова"""
        # Добавляем слово
        word_id = self.db.add_word(self.test_user_id, "удалить", "это слово")
        
        # Удаляем
        deleted = self.db.delete_word(word_id, self.test_user_id)
        
        self.assertTrue(deleted)
        
        # Проверяем что слово удалено
        words = self.db.get_user_words(self.test_user_id)
        self.assertEqual(len(words), 0)
    
    def test_duplicate_word(self):
        """Тест обработки дубликатов"""
        # Добавляем слово дважды
        word_id1 = self.db.add_word(self.test_user_id, "дубликат", "первое")
        word_id2 = self.db.add_word(self.test_user_id, "дубликат", "второе")
        
        # Должно быть только одно слово (обновленное)
        words = self.db.get_user_words(self.test_user_id)
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0]['definition'], "второе")


class TestConfig(unittest.TestCase):
    """Тесты конфигурации"""
    
    def test_env_file_exists(self):
        """Проверка наличия .env.example"""
        self.assertTrue(os.path.exists('.env.example'))
    
    def test_required_files(self):
        """Проверка наличия всех необходимых файлов"""
        required_files = [
            'main.py',
            'database.py',
            'config.py',
            'requirements.txt',
            'README.md',
            '.gitignore'
        ]
        
        for filename in required_files:
            with self.subTest(file=filename):
                self.assertTrue(
                    os.path.exists(filename),
                    f"Файл {filename} не найден"
                )


def run_tests():
    """Запуск всех тестов"""
    print("🧪 Запуск тестов...\n")
    
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем тесты
    suite.addTests(loader.loadTestsFromTestCase(TestDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))
    
    # Запускаем
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Результаты
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("✅ Все тесты пройдены успешно!")
    else:
        print("❌ Некоторые тесты провалились")
        print(f"   Провалено: {len(result.failures)}")
        print(f"   Ошибок: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
