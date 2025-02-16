import sqlite3
from datetime import datetime, timedelta
import threading
from logger import log_error
import os

class Database:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Database, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.db_file = 'bot.db'
        self._connection = None
        self._initialized = True
        self.init_database()
    
    def get_connection(self):
        """Получить соединение с базой данных"""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_file, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def init_database(self):
        """Инициализация базы данных"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            
            # Создаем все необходимые таблицы
            c.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT DEFAULT 'user',
                    messages_count INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    balance INTEGER DEFAULT 0,
                    reputation INTEGER DEFAULT 0,
                    warnings INTEGER DEFAULT 0,
                    is_muted INTEGER DEFAULT 0,
                    mute_end TIMESTAMP,
                    last_daily TIMESTAMP,
                    nickname TEXT,
                    reg_date TIMESTAMP,
                    invited_count INTEGER DEFAULT 0,
                    last_activity TIMESTAMP,
                    last_bug_report TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS marriages (
                    user1_id INTEGER,
                    user2_id INTEGER,
                    marriage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user1_id) REFERENCES users(user_id),
                    FOREIGN KEY (user2_id) REFERENCES users(user_id),
                    PRIMARY KEY (user1_id, user2_id)
                );

                CREATE TABLE IF NOT EXISTS bans (
                    user_id INTEGER,
                    chat_id INTEGER,
                    ban_time TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS warn_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    warned_by INTEGER,
                    reason TEXT,
                    timestamp TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    chat_id INTEGER,
                    message_type TEXT,
                    timestamp TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id INTEGER PRIMARY KEY,
                    quiet_mode INTEGER DEFAULT 0,
                    quiet_end TIMESTAMP,
                    welcome_message TEXT,
                    auto_warn INTEGER DEFAULT 0,
                    max_warnings INTEGER DEFAULT 3
                );

                CREATE TABLE IF NOT EXISTS bot_chats (
                    chat_id INTEGER PRIMARY KEY,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS word_filters (
                    chat_id INTEGER,
                    word TEXT,
                    added_by INTEGER,
                    added_time TIMESTAMP,
                    PRIMARY KEY (chat_id, word)
                );

                CREATE TABLE IF NOT EXISTS automod_settings (
                    chat_id INTEGER PRIMARY KEY,
                    spam_filter INTEGER DEFAULT 0,
                    caps_filter INTEGER DEFAULT 0,
                    links_filter INTEGER DEFAULT 0,
                    max_warns INTEGER DEFAULT 3,
                    action TEXT DEFAULT 'warn'
                );

                CREATE TABLE IF NOT EXISTS bug_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    description TEXT,
                    status TEXT,
                    report_date TIMESTAMP
                );
            ''')
            
            conn.commit()
            
            # Создаем индексы для оптимизации
            c.executescript('''
                CREATE INDEX IF NOT EXISTS idx_message_history_user_chat 
                ON message_history(user_id, chat_id);
                
                CREATE INDEX IF NOT EXISTS idx_warn_history_user 
                ON warn_history(user_id);
                
                CREATE INDEX IF NOT EXISTS idx_bans_user 
                ON bans(user_id);
                
                CREATE INDEX IF NOT EXISTS idx_users_role 
                ON users(role);
            ''')
            
            conn.commit()
            
        except Exception as e:
            log_error(f"Ошибка при инициализации базы данных: {str(e)}", exc_info=True)
            raise
    
    def backup_database(self):
        """Создание резервной копии базы данных"""
        try:
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            backup_file = f"{backup_dir}/bot_db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            
            conn = self.get_connection()
            backup = sqlite3.connect(backup_file)
            conn.backup(backup)
            backup.close()
            
            # Удаляем старые бэкапы (оставляем только 5 последних)
            backup_files = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
            if len(backup_files) > 5:
                for old_file in backup_files[:-5]:
                    os.remove(os.path.join(backup_dir, old_file))
                    
            return True
        except Exception as e:
            log_error(f"Ошибка при создании резервной копии: {str(e)}", exc_info=True)
            return False
    
    def execute(self, query, params=None):
        """Выполнить SQL-запрос"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            if params:
                c.execute(query, params)
            else:
                c.execute(query)
            conn.commit()
            return c
        except Exception as e:
            log_error(f"Ошибка при выполнении запроса: {str(e)}\nЗапрос: {query}\nПараметры: {params}", exc_info=True)
            raise
    
    def fetch_one(self, query, params=None):
        """Получить одну запись"""
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def fetch_all(self, query, params=None):
        """Получить все записи"""
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    def close(self):
        """Закрыть соединение с базой данных"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def get_message_count(self, user_id):
        """Получить количество сообщений пользователя"""
        try:
            result = self.fetch_one('''SELECT COUNT(*) as count 
                                     FROM message_history 
                                     WHERE user_id = ?''', (user_id,))
            return result['count'] if result else 0
        except Exception as e:
            log_error(f"Ошибка при получении количества сообщений: {str(e)}", exc_info=True)
            return 0

    def update_message_count(self, user_id, count):
        """Обновить количество сообщений пользователя"""
        try:
            self.execute('''UPDATE users 
                           SET messages_count = ? 
                           WHERE user_id = ?''', (count, user_id))
            return True
        except Exception as e:
            log_error(f"Ошибка при обновлении количества сообщений: {str(e)}", exc_info=True)
            return False

    def get_user_data(self, user_id):
        """Получить все данные пользователя"""
        try:
            result = self.fetch_one('''SELECT user_id, role, messages_count,
                                            level, xp, balance, reputation,
                                            warnings, nickname, reg_date,
                                            invited_count
                                     FROM users 
                                     WHERE user_id = ?''', (user_id,))
            if result:
                return dict(result)
            return None
        except Exception as e:
            log_error(f"Ошибка при получении данных пользователя: {str(e)}", exc_info=True)
            return None

    def get_user_role(self, user_id):
        """Получить роль пользователя"""
        try:
            result = self.fetch_one('SELECT role FROM users WHERE user_id = ?', (user_id,))
            return result['role'] if result else 'user'
        except Exception as e:
            log_error(f"Ошибка при получении роли пользователя: {str(e)}", exc_info=True)
            return 'user'

    def update_user_nickname(self, user_id, nickname):
        """Обновить ник пользователя"""
        try:
            self.execute('UPDATE users SET nickname = ? WHERE user_id = ?', 
                        (nickname, user_id))
            return True
        except Exception as e:
            log_error(f"Ошибка при обновлении ника пользователя: {str(e)}", exc_info=True)
            return False

    def get_users_with_nicknames(self):
        """Получить список пользователей с никами"""
        try:
            return self.fetch_all('''SELECT user_id, nickname 
                                   FROM users 
                                   WHERE nickname IS NOT NULL 
                                   ORDER BY nickname''')
        except Exception as e:
            log_error(f"Ошибка при получении списка пользователей с никами: {str(e)}", exc_info=True)
            return []

    def get_chat_settings(self, chat_id):
        """Получить настройки беседы"""
        try:
            result = self.fetch_one('''SELECT * FROM chat_settings 
                                     WHERE chat_id = ?''', (chat_id,))
            return dict(result) if result else None
        except Exception as e:
            log_error(f"Ошибка при получении настроек беседы: {str(e)}", exc_info=True)
            return None

    def update_chat_settings(self, chat_id, settings):
        """Обновить настройки беседы"""
        try:
            fields = ', '.join([f"{k} = ?" for k in settings.keys()])
            query = f'''INSERT OR REPLACE INTO chat_settings (chat_id, {fields})
                       VALUES (?, {', '.join(['?' for _ in settings])})'''
            values = [chat_id] + list(settings.values())
            self.execute(query, values)
            return True
        except Exception as e:
            log_error(f"Ошибка при обновлении настроек беседы: {str(e)}", exc_info=True)
            return False

    def get_top_users(self, category, limit=10):
        """Получить топ пользователей по категории"""
        try:
            if category not in ['level', 'messages', 'balance', 'rep']:
                return []
            
            field = {
                'level': 'level',
                'messages': 'messages_count',
                'balance': 'balance',
                'rep': 'reputation'
            }[category]
            
            return self.fetch_all(f'''SELECT user_id, {field} as value 
                                    FROM users 
                                    ORDER BY {field} DESC 
                                    LIMIT ?''', (limit,))
        except Exception as e:
            log_error(f"Ошибка при получении топа пользователей: {str(e)}", exc_info=True)
            return []

    def get_user_stats(self, user_id):
        """Получить статистику пользователя"""
        try:
            result = self.fetch_one('''SELECT messages_count, level, xp,
                                            balance, reputation, warnings,
                                            invited_count
                                     FROM users 
                                     WHERE user_id = ?''', (user_id,))
            return dict(result) if result else None
        except Exception as e:
            log_error(f"Ошибка при получении статистики пользователя: {str(e)}", exc_info=True)
            return None

    def add_user_if_not_exists(self, user_id):
        """Добавить пользователя, если его нет в базе"""
        try:
            result = self.fetch_one('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
            if not result:
                self.execute('''INSERT INTO users 
                              (user_id, messages_count, reg_date)
                              VALUES (?, 0, ?)''', 
                           (user_id, datetime.now()))
            return True
        except Exception as e:
            log_error(f"Ошибка при добавлении пользователя: {str(e)}", exc_info=True)
            return False

    def update_user_activity(self, user_id):
        """Обновить время последней активности пользователя"""
        try:
            self.execute('''UPDATE users 
                           SET last_activity = ? 
                           WHERE user_id = ?''', 
                        (datetime.now(), user_id))
            return True
        except Exception as e:
            log_error(f"Ошибка при обновлении активности пользователя: {str(e)}", exc_info=True)
            return False

    def get_active_users(self, hours=24):
        """Получить список активных пользователей за последние N часов"""
        try:
            time_threshold = datetime.now() - timedelta(hours=hours)
            return self.fetch_all('''SELECT DISTINCT user_id 
                                   FROM message_history 
                                   WHERE timestamp > ?''', 
                                (time_threshold,))
        except Exception as e:
            log_error(f"Ошибка при получении списка активных пользователей: {str(e)}", exc_info=True)
            return []

# Создаем глобальный экземпляр базы данных
db = Database() 