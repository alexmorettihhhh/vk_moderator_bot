import sqlite3
from datetime import datetime
from logger import log_error

def adapt_datetime(dt):
    """Convert datetime to string for SQLite storage"""
    return dt.isoformat()

def convert_datetime(s):
    """Convert string from SQLite to datetime"""
    try:
        return datetime.fromisoformat(s.decode())
    except (AttributeError, ValueError):
        return None

def update_database():
    """Обновляет структуру базы данных"""
    conn = None
    try:
        # Регистрируем адаптеры для корректной работы с datetime
        sqlite3.register_adapter(datetime, adapt_datetime)
        sqlite3.register_converter("TIMESTAMP", convert_datetime)
        
        conn = sqlite3.connect('bot.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES, timeout=20)
        conn.execute('PRAGMA foreign_keys = ON')
        c = conn.cursor()

        # Добавляем транзакцию
        with conn:
            # Добавляем новые колонки в таблицу users
            try:
                c.execute('ALTER TABLE users ADD COLUMN reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            except sqlite3.OperationalError:
                pass  # Колонка уже существует
                
            try:
                c.execute('ALTER TABLE users ADD COLUMN invited_count INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # Колонка уже существует

            # Обновляем reg_date для существующих пользователей, если оно NULL
            c.execute('UPDATE users SET reg_date = CURRENT_TIMESTAMP WHERE reg_date IS NULL')

            # Добавляем новые поля для статистики игр
            try:
                c.execute('ALTER TABLE users ADD COLUMN games_won INTEGER DEFAULT 0')
                c.execute('ALTER TABLE users ADD COLUMN games_lost INTEGER DEFAULT 0')
                c.execute('ALTER TABLE users ADD COLUMN total_winnings INTEGER DEFAULT 0')
                c.execute('ALTER TABLE users ADD COLUMN total_losses INTEGER DEFAULT 0')
                c.execute('ALTER TABLE users ADD COLUMN tournament_points INTEGER DEFAULT 0')
                c.execute('ALTER TABLE users ADD COLUMN last_tournament_reward TIMESTAMP')
                c.execute('ALTER TABLE users ADD COLUMN jackpot_wins INTEGER DEFAULT 0')
                c.execute('ALTER TABLE users ADD COLUMN poker_wins INTEGER DEFAULT 0')
                c.execute('ALTER TABLE users ADD COLUMN biggest_win INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass

            # Добавляем таблицу настроек, если её нет
            c.execute('''CREATE TABLE IF NOT EXISTS settings
                        (key TEXT PRIMARY KEY,
                         value TEXT)''')

            # Добавляем начальные значения для игр
            c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("lottery_jackpot", "1000")')
            c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("jackpot_bank", "0")')
            c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("tournament_end", NULL)')
            c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("tournament_players", "{}")')
            c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("poker_rake", "5")')
            c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("slots_jackpot", "10000")')

            # Создаем таблицу для турнирной статистики
            c.execute('''CREATE TABLE IF NOT EXISTS tournament_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER,
                         tournament_date DATE,
                         place INTEGER,
                         points INTEGER,
                         reward INTEGER,
                         FOREIGN KEY (user_id) REFERENCES users(user_id))''')

            # Создаем таблицу для истории джекпотов
            c.execute('''CREATE TABLE IF NOT EXISTS jackpot_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER,
                         amount INTEGER,
                         timestamp TIMESTAMP,
                         game_type TEXT,
                         FOREIGN KEY (user_id) REFERENCES users(user_id))''')

            # Создаем таблицу для покерных турниров
            c.execute('''CREATE TABLE IF NOT EXISTS poker_tournaments
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         start_time TIMESTAMP,
                         end_time TIMESTAMP,
                         buy_in INTEGER,
                         prize_pool INTEGER,
                         max_players INTEGER,
                         status TEXT DEFAULT 'pending')''')

            c.execute('''CREATE TABLE IF NOT EXISTS poker_tournament_players
                        (tournament_id INTEGER,
                         user_id INTEGER,
                         position INTEGER,
                         prize INTEGER,
                         FOREIGN KEY (tournament_id) REFERENCES poker_tournaments(id),
                         FOREIGN KEY (user_id) REFERENCES users(user_id),
                         PRIMARY KEY (tournament_id, user_id))''')

            # Добавляем новые достижения
            achievements = [
                ('🎰 Миллионер', 'Накопить 1,000,000 монет'),
                ('💎 Крупный выигрыш', 'Выиграть 100,000 монет за раз'),
                ('🏆 Профессиональный игрок', 'Выиграть 100 игр'),
                ('👑 Легенда казино', 'Накопить 5,000,000 монет'),
                ('🌟 Джекпот', 'Выиграть 500,000 монет за раз'),
                ('🎲 Заядлый игрок', 'Сыграть 1,000 игр'),
                ('♠️ Покерный профи', 'Выиграть 50 раз в покер'),
                ('💰 Везунчик', 'Выиграть джекпот 3 раза'),
                ('🏅 Турнирный боец', 'Занять первое место в 5 турнирах')
            ]
            
            c.execute('''CREATE TABLE IF NOT EXISTS achievement_types
                        (type TEXT PRIMARY KEY,
                         description TEXT)''')
            
            for achievement_type, description in achievements:
                c.execute('INSERT OR IGNORE INTO achievement_types (type, description) VALUES (?, ?)',
                         (achievement_type, description))

            # Добавляем новые поля в существующие таблицы
            try:
                c.execute('ALTER TABLE chat_settings ADD COLUMN antispam_enabled INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # Колонка уже существует

            try:
                c.execute('ALTER TABLE users ADD COLUMN last_activity TIMESTAMP')
            except sqlite3.OperationalError:
                pass

            try:
                c.execute('ALTER TABLE bug_reports ADD COLUMN status TEXT DEFAULT "new"')
            except sqlite3.OperationalError:
                pass

            # Создаем таблицу для истории сообщений
            c.execute('''CREATE TABLE IF NOT EXISTS message_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER,
                         chat_id INTEGER,
                         message_type TEXT,
                         timestamp TIMESTAMP,
                         FOREIGN KEY (user_id) REFERENCES users(user_id),
                         FOREIGN KEY (chat_id) REFERENCES bot_chats(chat_id))''')

            # Создаем таблицу для статистики чатов
            c.execute('''CREATE TABLE IF NOT EXISTS chat_stats
                        (chat_id INTEGER PRIMARY KEY,
                         messages_today INTEGER DEFAULT 0,
                         active_users_today INTEGER DEFAULT 0,
                         last_update TIMESTAMP,
                         FOREIGN KEY (chat_id) REFERENCES bot_chats(chat_id))''')

            # Создаем таблицу для логов модерации
            c.execute('''CREATE TABLE IF NOT EXISTS moderation_logs
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         moderator_id INTEGER,
                         action TEXT,
                         target_id INTEGER,
                         chat_id INTEGER,
                         reason TEXT,
                         timestamp TIMESTAMP,
                         FOREIGN KEY (moderator_id) REFERENCES users(user_id),
                         FOREIGN KEY (chat_id) REFERENCES bot_chats(chat_id))''')

            # Создаем таблицу для антиспам настроек
            c.execute('''CREATE TABLE IF NOT EXISTS antispam_settings
                        (chat_id INTEGER PRIMARY KEY,
                         message_interval REAL DEFAULT 1.0,
                         max_messages INTEGER DEFAULT 5,
                         check_period INTEGER DEFAULT 10,
                         max_warnings INTEGER DEFAULT 3,
                         mute_duration INTEGER DEFAULT 300,
                         max_similar_messages INTEGER DEFAULT 3,
                         similarity_threshold REAL DEFAULT 0.85,
                         FOREIGN KEY (chat_id) REFERENCES bot_chats(chat_id))''')

            # Создаем основные таблицы, если они не существуют
            c.execute('''CREATE TABLE IF NOT EXISTS bans
                        (user_id INTEGER,
                         chat_id INTEGER,
                         ban_time TIMESTAMP,
                         PRIMARY KEY (user_id, chat_id))''')

            c.execute('''CREATE TABLE IF NOT EXISTS warn_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER,
                         warned_by INTEGER,
                         reason TEXT,
                         timestamp TIMESTAMP)''')

            c.execute('''CREATE TABLE IF NOT EXISTS message_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER,
                         chat_id INTEGER,
                         message_type TEXT,
                         timestamp TIMESTAMP)''')

            # Создаем таблицу для истории репутации
            c.execute('''CREATE TABLE IF NOT EXISTS reputation_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         from_user_id INTEGER,
                         to_user_id INTEGER,
                         amount INTEGER,
                         reason TEXT,
                         timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         FOREIGN KEY (from_user_id) REFERENCES users(user_id),
                         FOREIGN KEY (to_user_id) REFERENCES users(user_id))''')

            # Создаем индексы
            c.execute('CREATE INDEX IF NOT EXISTS idx_message_history_user ON message_history(user_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_message_history_chat ON message_history(chat_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_message_history_time ON message_history(timestamp)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_bans_user ON bans(user_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_bans_chat ON bans(chat_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_warn_history_user ON warn_history(user_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_reputation_history_timestamp ON reputation_history(timestamp)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_reputation_history_users ON reputation_history(from_user_id, to_user_id)')

            # Обновляем существующие записи
            c.execute('UPDATE users SET last_activity = ? WHERE last_activity IS NULL', (datetime.now(),))
            c.execute('UPDATE chat_settings SET antispam_enabled = 0 WHERE antispam_enabled IS NULL')

            # Создаем триггер для автоматического обновления last_activity
            c.execute('''CREATE TRIGGER IF NOT EXISTS update_user_activity
                        AFTER INSERT ON message_history
                        BEGIN
                            UPDATE users 
                            SET last_activity = NEW.timestamp 
                            WHERE user_id = NEW.user_id;
                        END''')

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        log_error(f"Ошибка SQLite при обновлении базы данных: {str(e)}", exc_info=True)
        return False
    except Exception as e:
        log_error(f"Неожиданная ошибка при обновлении базы данных: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    if update_database():
        print("✅ База данных успешно обновлена")
    else:
        print("❌ Произошла ошибка при обновлении базы данных") 