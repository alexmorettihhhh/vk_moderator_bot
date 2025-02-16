import sqlite3
from datetime import datetime, timedelta
from vk_api.utils import get_random_id
import random
from utils import extract_user_id

def cmd_profile(vk, event, args):
    try:
        if args:
            target = ' '.join(args)
            user_id = extract_user_id(vk, target)
            if not user_id:
                return "❌ Не удалось определить пользователя"
        else:
            user_id = event.obj.message['from_id']
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Get user info
        c.execute('''SELECT nickname, level, xp, messages_count, balance, reputation 
                    FROM users WHERE user_id = ?''', (user_id,))
        result = c.fetchone()
        
        if not result:
            return "⚠️ Пользователь не найден в базе данных"
        
        nickname, level, xp, messages, balance, reputation = result
        
        # Get marriage info
        c.execute('''SELECT user2_id, marriage_date FROM marriages 
                    WHERE user1_id = ? OR user2_id = ?''', (user_id, user_id))
        marriage = c.fetchone()
        
        # Get achievements
        c.execute('SELECT achievement_type FROM achievements WHERE user_id = ?', (user_id,))
        achievements = c.fetchall()
        
        conn.close()
        
        # Format message
        user_info = vk.users.get(user_ids=user_id)[0]
        message = f"👤 Профиль пользователя @id{user_id} ({user_info['first_name']}):\n\n"
        if nickname:
            message += f"🏷 Ник: {nickname}\n"
        message += f"📊 Уровень: {level} ({xp}/{level * 1000} XP)\n"
        message += f"💬 Сообщений: {messages}\n"
        message += f"💰 Баланс: {balance} монет\n"
        message += f"👍 Репутация: {reputation}\n"
        
        if marriage:
            partner_id = marriage[0]
            partner_info = vk.users.get(user_ids=partner_id)[0]
            marriage_date = datetime.strptime(marriage[1], '%Y-%m-%d %H:%M:%S.%f')
            message += f"💑 В браке с @id{partner_id} ({partner_info['first_name']}) с {marriage_date.strftime('%d.%m.%Y')}\n"
        
        if achievements:
            message += "\n🏆 Достижения:\n"
            for achievement in achievements:
                message += f"• {achievement[0]}\n"
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def cmd_give(vk, event, args):
    """Передача монет другому пользователю"""
    if len(args) < 2:
        return "⚠️ Использование: /give [ID] [количество]"
    
    try:
        target = args[0]
        amount = int(args[1])
        from_id = event.obj.message['from_id']
        
        if amount < 1:
            return "⚠️ Минимальная сумма для передачи: 1 монета"
        
        # Извлекаем ID пользователя
        to_id = extract_user_id(vk, target)
        if not to_id:
            return "❌ Не удалось определить пользователя"
        
        if from_id == to_id:
            return "❌ Вы не можете передать монеты самому себе"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс отправителя
        c.execute('SELECT balance FROM users WHERE user_id = ?', (from_id,))
        sender_balance = c.fetchone()
        
        if not sender_balance or sender_balance[0] < amount:
            return "❌ Недостаточно монет для передачи"
        
        # Переводим монеты
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, from_id))
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, to_id))
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[to_id])[0]
        return f"💰 Вы успешно передали {amount} монет пользователю @id{to_id} ({user_info['first_name']})"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
    
def cmd_nickname(vk, event, args):
    """Установка или изменение ника пользователя"""
    if not args:
        return "⚠️ Укажите ник"
    
    try:
        user_id = event.obj.message['from_id']
        nickname = ' '.join(args)
        
        if len(nickname) > 20:
            return "⚠️ Максимальная длина ника: 20 символов"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Обновляем ник
        c.execute('UPDATE users SET nickname = ? WHERE user_id = ?', (nickname, user_id))
        
        conn.commit()
        conn.close()
        
        return f"🏷 Ваш ник успешно изменен на: {nickname}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
    


def cmd_achievements(vk, event):
    """Просмотр достижений пользователя"""
    try:
        user_id = event.obj.message['from_id']
        
        conn = sqlite3.connect('bot.db', detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        
        # Получаем достижения
        c.execute('''SELECT a.achievement_type, a.achievement_date, at.description 
                    FROM achievements a
                    JOIN achievement_types at ON a.achievement_type = at.type
                    WHERE a.user_id = ?
                    ORDER BY a.achievement_date DESC''', (user_id,))
        achievements = c.fetchall()
        
        if not achievements:
            return "🏆 У вас пока нет достижений"
        
        message = "🏆 Ваши достижения:\n\n"
        for achievement_type, achievement_date, description in achievements:
            formatted_date = achievement_date.strftime('%d.%m.%Y')
            message += f"• {achievement_type} - {description}\n  Получено: {formatted_date}\n"
        
        # Получаем прогресс для незаработанных достижений
        c.execute('''SELECT total_winnings, games_won, games_lost, 
                     jackpot_wins, poker_wins, biggest_win,
                     (SELECT COUNT(*) FROM tournament_history 
                      WHERE user_id = ? AND place = 1) as tournament_wins
                     FROM users WHERE user_id = ?''', (user_id, user_id))
        stats = c.fetchone()
        
        if stats:
            total_winnings, games_won, games_lost, jackpot_wins, poker_wins, biggest_win, tournament_wins = stats
            
            # Проверяем прогресс для каждого недостигнутого достижения
            message += "\n📊 Прогресс достижений:\n"
            earned_types = {ach[0] for ach in achievements}
            
            progress = [
                ('🎰 Миллионер', total_winnings, 1000000, 'монет накоплено'),
                ('💎 Крупный выигрыш', biggest_win, 100000, 'монет за раз'),
                ('🏆 Профессиональный игрок', games_won, 100, 'побед'),
                ('👑 Легенда казино', total_winnings, 5000000, 'монет накоплено'),
                ('♠️ Покерный профи', poker_wins, 50, 'побед в покер'),
                ('💰 Везунчик', jackpot_wins, 3, 'джекпота выиграно'),
                ('🏅 Турнирный боец', tournament_wins, 5, 'побед в турнирах'),
                ('🎲 Заядлый игрок', games_won + games_lost, 1000, 'игр сыграно')
            ]
            
            for ach_type, current, required, metric in progress:
                if ach_type not in earned_types:
                    percentage = min(100, int(current * 100 / required))
                    message += f"• {ach_type}: {current}/{required} {metric} ({percentage}%)\n"
        
        conn.close()
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_daily(vk, event):
    try:
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Check last daily claim
        c.execute('SELECT last_daily FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        
        if result and result[0]:
            last_daily = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S.%f')
            if datetime.now() - last_daily < timedelta(days=1):
                next_daily = last_daily + timedelta(days=1)
                return f"⏳ Вы уже получили ежедневную награду. Следующая будет доступна {next_daily.strftime('%d.%m.%Y в %H:%M')}"
        
        # Give reward
        reward = random.randint(100, 500)
        c.execute('''UPDATE users 
                    SET balance = balance + ?, last_daily = ? 
                    WHERE user_id = ?''', (reward, datetime.now(), user_id))
        
        conn.commit()
        conn.close()
        
        return f"💰 Вы получили ежедневную награду: {reward} монет!"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_marry(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        user_id = event.obj.message['from_id']
        target = ' '.join(args)
        
        # Извлекаем ID пользователя из упоминания или обычного ID
        partner_id = extract_user_id(vk, target)
        
        if not partner_id:
            return "❌ Не удалось определить пользователя"
        
        if user_id == partner_id:
            return "❌ Вы не можете заключить брак с самим собой"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Check if either user is already married
        c.execute('''SELECT 1 FROM marriages 
                    WHERE user1_id IN (?, ?) OR user2_id IN (?, ?)''', 
                    (user_id, partner_id, user_id, partner_id))
        if c.fetchone():
            return "❌ Один из пользователей уже состоит в браке"
        
        # Create marriage
        c.execute('''INSERT INTO marriages (user1_id, user2_id, marriage_date)
                    VALUES (?, ?, ?)''', (user_id, partner_id, datetime.now()))
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id, partner_id])
        return f"💑 Поздравляем! @id{user_id} ({user_info[0]['first_name']}) и @id{partner_id} ({user_info[1]['first_name']}) теперь в браке!"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_divorce(vk, event):
    try:
        user_id = event.obj.message['from_id']
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Find and delete marriage
        c.execute('''DELETE FROM marriages 
                    WHERE user1_id = ? OR user2_id = ?''', (user_id, user_id))
        
        if c.rowcount == 0:
            return "❌ Вы не состоите в браке"
        
        conn.commit()
        conn.close()
        
        return "💔 Брак расторгнут"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_rep(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя и причину"
    
    try:
        from_id = event.obj.message['from_id']
        target = args[0]
        reason = ' '.join(args[1:]) if len(args) > 1 else "Без причины"
        
        # Извлекаем ID пользователя
        to_id = extract_user_id(vk, target)
        if not to_id:
            return "❌ Не удалось определить пользователя"
        
        if from_id == to_id:
            return "❌ Вы не можете изменить репутацию самому себе"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Add reputation point and history
        c.execute('''UPDATE users 
                    SET reputation = reputation + 1 
                    WHERE user_id = ?''', (to_id,))
        
        c.execute('''INSERT INTO reputation_history 
                    (from_user_id, to_user_id, amount, reason, timestamp)
                    VALUES (?, ?, 1, ?, ?)''', 
                    (from_id, to_id, reason, datetime.now()))
        
        conn.commit()
        
        # Get new reputation value
        c.execute('SELECT reputation FROM users WHERE user_id = ?', (to_id,))
        new_rep = c.fetchone()[0]
        
        conn.close()
        
        user_info = vk.users.get(user_ids=[to_id])[0]
        return f"👍 Вы повысили репутацию пользователя @id{to_id} ({user_info['first_name']}). Текущая репутация: {new_rep}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_game(vk, event, args):
    if not args:
        return "⚠️ Использование: /game [камень/ножницы/бумага]"
    
    try:
        user_choice = args[0].lower()
        choices = ['камень', 'ножницы', 'бумага']
        
        if user_choice not in choices:
            return "⚠️ Выберите: камень, ножницы или бумага"
        
        bot_choice = random.choice(choices)
        
        # Determine winner
        if user_choice == bot_choice:
            result = "🤝 Ничья!"
        elif ((user_choice == 'камень' and bot_choice == 'ножницы') or
              (user_choice == 'ножницы' and bot_choice == 'бумага') or
              (user_choice == 'бумага' and bot_choice == 'камень')):
            result = "🎉 Вы победили!"
        else:
            result = "😢 Вы проиграли!"
        
        return f"Вы выбрали: {user_choice}\nБот выбрал: {bot_choice}\n{result}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_top(vk, event, args):
    try:
        category = args[0] if args else 'level'
        
        categories = {
            'level': ('уровню', 'level'),
            'messages': ('сообщениям', 'messages_count'),
            'balance': ('балансу', 'balance'),
            'rep': ('репутации', 'reputation')
        }
        
        if category not in categories:
            return "⚠️ Доступные категории: level, messages, balance, rep"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute(f'''SELECT user_id, {categories[category][1]} 
                    FROM users 
                    ORDER BY {categories[category][1]} DESC 
                    LIMIT 10''')
        top_users = c.fetchall()
        conn.close()
        
        if not top_users:
            return "📊 Статистика пока недоступна"
        
        message = f"🏆 Топ 10 по {categories[category][0]}:\n\n"
        
        user_ids = [user[0] for user in top_users]
        users_info = vk.users.get(user_ids=user_ids)
        users_dict = {user['id']: user for user in users_info}
        
        for i, (user_id, value) in enumerate(top_users, 1):
            user = users_dict.get(user_id, {'first_name': 'Unknown', 'last_name': 'User'})
            message += f"{i}. @id{user_id} ({user['first_name']}): {value}\n"
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}" 