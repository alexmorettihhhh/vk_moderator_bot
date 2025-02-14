import sqlite3
from datetime import datetime
import random
from vk_api.utils import get_random_id
from utils import extract_user_id

def cmd_slots(vk, event, args):
    """Игра в слоты"""
    if not args:
        return "⚠️ Укажите ставку"
    
    try:
        bet = int(args[0])
        if bet < 1:
            return "⚠️ Минимальная ставка: 1 монета"
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = c.fetchone()
        
        if not balance or balance[0] < bet:
            return "❌ Недостаточно монет"
        
        # Символы для слотов
        symbols = ['🍎', '🍋', '🍒', '7️⃣', '💎']
        weights = [0.4, 0.3, 0.15, 0.1, 0.05]  # Вероятности выпадения
        
        # Крутим слоты
        result = random.choices(symbols, weights=weights, k=3)
        
        # Проверяем выигрыш
        if result[0] == result[1] == result[2]:
            multiplier = {
                '🍎': 2,
                '🍋': 3,
                '🍒': 5,
                '7️⃣': 10,
                '💎': 20
            }[result[0]]
            win = bet * multiplier
            message = f"🎰 {' '.join(result)}\n💰 Выигрыш: {win} монет (x{multiplier})"
        else:
            win = -bet
            message = f"🎰 {' '.join(result)}\n💸 Проигрыш: {bet} монет"
        
        # Обновляем баланс
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (win, user_id))
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_duel(vk, event, args):
    """Дуэль между игроками"""
    if len(args) < 2:
        return "⚠️ Использование: /duel [пользователь] [ставка]"
    
    try:
        target = args[0]
        bet = int(args[1])
        user_id = event.obj.message['from_id']
        
        # Извлекаем ID пользователя
        opponent_id = extract_user_id(vk, target)
        if not opponent_id:
            return "❌ Не удалось определить пользователя"
        
        if bet < 1:
            return "⚠️ Минимальная ставка: 1 монета"
        if user_id == opponent_id:
            return "❌ Нельзя драться с самим собой"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем балансы обоих игроков
        c.execute('SELECT balance FROM users WHERE user_id IN (?, ?)',
                 (user_id, opponent_id))
        balances = c.fetchall()
        
        if len(balances) != 2 or any(b[0] < bet for b in balances):
            return "❌ Недостаточно монет у одного из игроков"
        
        # Определяем победителя
        winner_id = random.choice([user_id, opponent_id])
        loser_id = opponent_id if winner_id == user_id else user_id
        
        # Обновляем балансы
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (bet, winner_id))
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?',
                 (bet, loser_id))
        
        conn.commit()
        conn.close()
        
        # Получаем информацию о пользователях
        users_info = vk.users.get(user_ids=[winner_id, loser_id])
        winner_info = next(u for u in users_info if u['id'] == winner_id)
        loser_info = next(u for u in users_info if u['id'] == loser_id)
        
        return (f"⚔️ Дуэль!\n"
                f"🏆 Победитель: @id{winner_id} ({winner_info['first_name']})\n"
                f"😢 Проигравший: @id{loser_id} ({loser_info['first_name']})\n"
                f"💰 Выигрыш: {bet} монет")
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_wheel(vk, event, args):
    """Колесо фортуны"""
    if not args:
        return "⚠️ Укажите ставку и цвет (red/black/green)"
    
    try:
        bet = int(args[0])
        color = args[1].lower() if len(args) > 1 else None
        
        if bet < 1:
            return "⚠️ Минимальная ставка: 1 монета"
        if color not in ['red', 'black', 'green']:
            return "⚠️ Выберите цвет: red, black или green"
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = c.fetchone()
        
        if not balance or balance[0] < bet:
            return "❌ Недостаточно монет"
        
        # Определяем результат
        result = random.choices(['red', 'black', 'green'], weights=[0.45, 0.45, 0.1])[0]
        
        # Проверяем выигрыш
        if result == color:
            multiplier = 14 if color == 'green' else 2
            win = bet * multiplier
            message = f"🎡 Выпало: {result}\n💰 Выигрыш: {win} монет (x{multiplier})"
        else:
            win = -bet
            message = f"🎡 Выпало: {result}\n💸 Проигрыш: {bet} монет"
        
        # Обновляем баланс
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (win, user_id))
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_flip(vk, event, args):
    """Подбрасывание монетки"""
    if not args:
        return "⚠️ Укажите ставку и сторону (heads/tails)"
    
    try:
        bet = int(args[0])
        side = args[1].lower() if len(args) > 1 else None
        
        if bet < 1:
            return "⚠️ Минимальная ставка: 1 монета"
        if side not in ['heads', 'tails']:
            return "⚠️ Выберите сторону: heads или tails"
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = c.fetchone()
        
        if not balance or balance[0] < bet:
            return "❌ Недостаточно монет"
        
        # Подбрасываем монетку
        result = random.choice(['heads', 'tails'])
        
        # Проверяем выигрыш
        if result == side:
            win = bet
            message = f"🎲 Выпало: {result}\n💰 Выигрыш: {win} монет"
        else:
            win = -bet
            message = f"🎲 Выпало: {result}\n💸 Проигрыш: {bet} монет"
        
        # Обновляем баланс
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (win, user_id))
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}" 