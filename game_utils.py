import sqlite3
from datetime import datetime, timedelta
from logger import log_error
import json

class GameCache:
    def __init__(self, max_size=1000):
        self.cache = {}
        self.max_size = max_size
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(minutes=5):
                return value
            del self.cache[key]
        return None
    
    def set(self, key, value):
        if len(self.cache) >= self.max_size:
            # Удаляем старые записи
            now = datetime.now()
            self.cache = {k: v for k, v in self.cache.items() 
                         if now - v[1] < timedelta(minutes=5)}
        self.cache[key] = (value, datetime.now())

# Создаем глобальный кэш
game_cache = GameCache()

def validate_bet(bet, min_bet=1, max_bet=1000000):
    """Проверка корректности ставки"""
    try:
        bet = int(bet)  # Добавляем преобразование в int
        if bet < min_bet:
            raise ValueError(f"Минимальная ставка: {min_bet} монет")
        if bet > max_bet:
            raise ValueError(f"Максимальная ставка: {max_bet} монет")
        return True
    except ValueError:
        raise ValueError("Ставка должна быть целым числом")

def check_game_limits(conn, user_id, game_type):
    """Проверка лимитов на игры"""
    try:
        c = conn.cursor()
        now = datetime.now()
        
        # Проверяем временные ограничения
        limits = {
            'slots': {'per_hour': 50, 'cooldown': 3},  # 50 игр в час, 3 секунды между играми
            'poker': {'per_hour': 30, 'cooldown': 5},
            'blackjack': {'per_hour': 40, 'cooldown': 4},
            'dice': {'per_hour': 60, 'cooldown': 2}
        }
        
        game_limits = limits.get(game_type, {'per_hour': 100, 'cooldown': 2})
        
        # Проверяем количество игр за последний час
        hour_ago = now - timedelta(hours=1)
        c.execute("""SELECT COUNT(*), MAX(timestamp) 
                    FROM game_history 
                    WHERE user_id = ? AND game_type = ? AND timestamp > ?""",
                    (user_id, game_type, hour_ago))
        result = c.fetchone()
        count = result[0] if result else 0
        last_game = result[1] if result and result[1] else None
        
        if count >= game_limits['per_hour']:
            return False, f"⚠️ Достигнут лимит игр в {game_type} на час"
        
        if last_game:
            last_game = datetime.fromisoformat(str(last_game))  # Добавляем преобразование в строку
            if (now - last_game).total_seconds() < game_limits['cooldown']:
                return False, f"⚠️ Подождите {game_limits['cooldown']} секунд между играми"
        
        return True, None
    except Exception as e:
        log_error(f"Ошибка при проверке лимитов: {str(e)}", exc_info=True)
        return False, "❌ Ошибка при проверке лимитов"

def check_suspicious_activity(conn, user_id):
    """Проверка на подозрительную активность"""
    try:
        c = conn.cursor()
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Проверяем количество крупных выигрышей за час
        c.execute("""SELECT COUNT(*) FROM jackpot_history 
                    WHERE user_id = ? AND timestamp > ? AND amount > 100000""",
                    (user_id, hour_ago))
        big_wins = c.fetchone()[0] if c.fetchone() else 0
        
        if big_wins > 3:
            return False, "Обнаружена подозрительная активность"
        
        # Проверяем резкий рост баланса
        c.execute("""SELECT balance, total_winnings, total_losses 
                    FROM users WHERE user_id = ?""", (user_id,))
        result = c.fetchone()
        if not result:
            return True, None
            
        balance, winnings, losses = result
        
        if balance > winnings * 2 and balance > 1000000:
            return False, "Обнаружен аномальный рост баланса"
        
        return True, None
    except Exception as e:
        log_error(f"Ошибка при проверке активности: {str(e)}", exc_info=True)
        return True, None

def update_tournament_status(conn, user_id, points):
    """Обновление статуса турнира"""
    try:
        c = conn.cursor()
        with conn:
            c.execute('SELECT value FROM settings WHERE key = "tournament_players"')
            result = c.fetchone()
            players = eval(result[0]) if result else {}
            
            # Обновляем очки игрока
            players[str(user_id)] = players.get(str(user_id), 0) + points
            
            # Сохраняем обновленные данные
            c.execute('UPDATE settings SET value = ? WHERE key = "tournament_players"',
                     (json.dumps(players),))  # Используем json.dumps вместо str
            
            # Обновляем статистику игрока
            c.execute("""UPDATE users 
                        SET tournament_points = tournament_points + ? 
                        WHERE user_id = ?""", (points, user_id))
            
            # Логируем обновление
            c.execute("""INSERT INTO tournament_history 
                        (user_id, tournament_date, points) 
                        VALUES (?, ?, ?)""",
                        (user_id, datetime.now(), points))
    except Exception as e:
        log_error(f"Ошибка при обновлении турнира: {str(e)}", exc_info=True)
        conn.rollback()  # Добавляем откат транзакции при ошибке
