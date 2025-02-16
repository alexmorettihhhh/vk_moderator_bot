import sqlite3
from datetime import datetime, timedelta
import random
from vk_api.utils import get_random_id
from utils import extract_user_id
import json
from logger import log_error

def update_user_stats(conn, user_id, win_amount):
    """Обновляет статистику игр пользователя"""
    try:
        c = conn.cursor()
        with conn:  # Используем контекстный менеджер для транзакций
            if win_amount > 0:
                c.execute('''UPDATE users 
                            SET games_won = games_won + 1,
                                total_winnings = total_winnings + ?,
                                biggest_win = CASE 
                                    WHEN ? > biggest_win THEN ?
                                    ELSE biggest_win
                                END
                            WHERE user_id = ?''', 
                         (win_amount, win_amount, win_amount, user_id))
            else:
                c.execute('''UPDATE users 
                            SET games_lost = games_lost + 1,
                                total_losses = total_losses + ?
                            WHERE user_id = ?''', 
                         (abs(win_amount), user_id))
    except sqlite3.Error as e:
        log_error(f"Ошибка при обновлении статистики: {str(e)}", exc_info=True)
        raise

def check_achievement(conn, user_id, win_amount, game_type=None):
    """Проверяет и выдает достижения за игры"""
    c = conn.cursor()
    
    # Проверяем статистику пользователя
    c.execute('''SELECT total_winnings, games_won, games_lost, 
                 jackpot_wins, poker_wins, biggest_win,
                 (SELECT COUNT(*) FROM tournament_history 
                  WHERE user_id = ? AND place = 1) as tournament_wins
                 FROM users WHERE user_id = ?''', (user_id, user_id))
    result = c.fetchone()
    if not result:
        return []
    
    total_winnings, games_won, games_lost, jackpot_wins, poker_wins, biggest_win, tournament_wins = result
    
    achievements = []
    # Проверяем все возможные достижения
    if total_winnings >= 1000000:
        achievements.append('🎰 Миллионер')
    if win_amount >= 100000:
        achievements.append('💎 Крупный выигрыш')
    if games_won >= 100:
        achievements.append('🏆 Профессиональный игрок')
    if total_winnings >= 5000000:
        achievements.append('👑 Легенда казино')
    if win_amount >= 500000:
        achievements.append('🌟 Джекпот')
    if games_won + games_lost >= 1000:
        achievements.append('🎲 Заядлый игрок')
    if poker_wins >= 50:
        achievements.append('♠️ Покерный профи')
    if jackpot_wins >= 3:
        achievements.append('💰 Везунчик')
    if tournament_wins >= 5:
        achievements.append('🏅 Турнирный боец')
    
    # Добавляем достижения в базу
    for achievement in achievements:
        c.execute('''INSERT OR IGNORE INTO achievements 
                    (user_id, achievement_type, achievement_date)
                    VALUES (?, ?, ?)''', (user_id, achievement, datetime.now()))
    
    # Записываем крупные выигрыши в историю
    if win_amount >= 100000:
        c.execute('''INSERT INTO jackpot_history 
                    (user_id, amount, timestamp, game_type)
                    VALUES (?, ?, ?, ?)''', 
                    (user_id, win_amount, datetime.now(), game_type))
    
    return achievements

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
        
        # Символы для слотов с улучшенными шансами
        symbols = ['🍎', '🍋', '🍒', '7️⃣', '💎', '🎰']
        weights = [0.35, 0.25, 0.20, 0.10, 0.07, 0.03]
        
        # Крутим слоты
        result = random.choices(symbols, weights=weights, k=3)
        
        # Проверяем выигрыш
        if result[0] == result[1] == result[2]:
            multiplier = {
                '🍎': 2,
                '🍋': 3,
                '🍒': 5,
                '7️⃣': 10,
                '💎': 20,
                '🎰': 50
            }[result[0]]
            win = bet * multiplier
            message = f"🎰 {' '.join(result)}\n💰 Выигрыш: {win} монет (x{multiplier})"
        elif result.count(result[0]) == 2 or result.count(result[1]) == 2:
            # Выигрыш за две одинаковые
            win = bet
            message = f"🎰 {' '.join(result)}\n💰 Маленький выигрыш: {win} монет"
        else:
            win = -bet
            message = f"🎰 {' '.join(result)}\n💸 Проигрыш: {bet} монет"
        
        # Обновляем баланс и статистику
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (win, user_id))
        update_user_stats(conn, user_id, win)
        
        # Проверяем достижения
        achievements = check_achievement(conn, user_id, win)
        if achievements:
            message += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def cmd_dice(vk, event, args):
    """Игра в кости с другим игроком"""
    if len(args) < 2:
        return "⚠️ Использование: /dice [ID] [ставка]"
    
    try:
        user_id = event.obj.message['from_id']
        target = args[0]
        bet = int(args[1])
        
        if bet < 1:
            return "⚠️ Минимальная ставка: 1 монета"
        
        # Извлекаем ID оппонента
        opponent_id = extract_user_id(vk, target)
        if not opponent_id:
            return "❌ Не удалось определить пользователя"
        
        if user_id == opponent_id:
            return "❌ Вы не можете играть сами с собой"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс обоих игроков
        c.execute('SELECT user_id, balance FROM users WHERE user_id IN (?, ?)', (user_id, opponent_id))
        balances = {row[0]: row[1] for row in c.fetchall()}
        
        if user_id not in balances:
            return "❌ У вас нет аккаунта в боте"
        if opponent_id not in balances:
            opponent_info = vk.users.get(user_ids=[opponent_id])[0]
            return f"❌ У пользователя @id{opponent_id} ({opponent_info['first_name']}) нет аккаунта в боте"
        
        if balances[user_id] < bet:
            return f"❌ У вас недостаточно монет (нужно {bet}, а у вас {balances[user_id]})"
        if balances[opponent_id] < bet:
            opponent_info = vk.users.get(user_ids=[opponent_id])[0]
            return f"❌ У пользователя @id{opponent_id} ({opponent_info['first_name']}) недостаточно монет (нужно {bet}, а у него {balances[opponent_id]})"
        
        # Бросаем кости
        user_roll = random.randint(1, 6)
        opponent_roll = random.randint(1, 6)
        
        # Определяем победителя
        if user_roll > opponent_roll:
            winner_id = user_id
            loser_id = opponent_id
        elif opponent_roll > user_roll:
            winner_id = opponent_id
            loser_id = user_id
        else:
            return "🎲 Ничья! Оба игрока выбросили " + str(user_roll)
        
        # Обновляем балансы
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bet, winner_id))
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (bet, loser_id))
        
        # Обновляем статистику
        c.execute('UPDATE users SET games_won = games_won + 1 WHERE user_id = ?', (winner_id,))
        c.execute('UPDATE users SET games_lost = games_lost + 1 WHERE user_id = ?', (loser_id,))
        
        conn.commit()
        conn.close()
        
        # Получаем информацию о пользователях
        users_info = vk.users.get(user_ids=[user_id, opponent_id])
        user_name = users_info[0]['first_name']
        opponent_name = users_info[1]['first_name']
        
        return (f"🎲 Результаты игры в кости:\n"
                f"@id{user_id} ({user_name}): {user_roll}\n"
                f"@id{opponent_id} ({opponent_name}): {opponent_roll}\n\n"
                f"Победитель: @id{winner_id} (+{bet} монет)")
                
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
    

def cmd_russian_roulette(vk, event, args):
    """Русская рулетка"""
    if not args:
        return "⚠️ Укажите ставку"
    
    try:
        bet = int(args[0])
        user_id = event.obj.message['from_id']
        
        if bet < 1:
            return "⚠️ Минимальная ставка: 1 монета"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = c.fetchone()
        
        if not balance or balance[0] < bet:
            return "❌ Недостаточно монет"
        
        # Выбираем случайное число от 1 до 6
        bullet = random.randint(1, 6)
        trigger = random.randint(1, 6)
        
        if bullet == trigger:
            win = -bet
            message = f"🔫 *Выстрел* 💀\n💸 Вы проиграли: {bet} монет"
        else:
            win = bet * 5  # Если выжили, получаем 5x ставку
            message = f"🔫 *Щелчок* ✅\n💰 Вы выжили! Выигрыш: {win} монет"
        
        # Обновляем баланс
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (win, user_id))
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
    


def cmd_blackjack(vk, event, args):
    """Игра в блэкджек"""
    if not args:
        return "⚠️ Использование: /blackjack [ставка] [действие: hit/stand]"
    
    try:
        bet = int(args[0])
        action = args[1].lower() if len(args) > 1 else 'start'
        
        # Валидация ставки
        validate_bet(bet, min_bet=50, max_bet=100000)
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db', detect_types=sqlite3.PARSE_DECLTYPES)
        
        try:
            # Проверяем лимиты
            can_play, limit_msg = check_game_limits(conn, user_id, 'blackjack')
            if not can_play:
                return limit_msg
                
            # Проверяем подозрительную активность
            is_safe, suspicious_msg = check_suspicious_activity(conn, user_id)
            if not is_safe:
                return suspicious_msg
            
            c = conn.cursor()
            
            # Проверяем баланс
            c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            balance = c.fetchone()
            
            if not balance or balance[0] < bet:
                return "❌ Недостаточно монет"
            
            def calculate_hand_value(cards):
                """Подсчет значения руки с учетом тузов"""
                value = 0
                aces = 0
                for card in cards:
                    if card == 11:  # Туз
                        aces += 1
                        value += 11
                    else:
                        value += card
                
                # Пересчитываем тузы как 1, если сумма больше 21
                while value > 21 and aces > 0:
                    value -= 10
                    aces -= 1
                
                return value
            
            if action == 'start':
                # Начинаем новую игру
                user_cards = [random.randint(1, 11), random.randint(1, 11)]
                dealer_cards = [random.randint(1, 11)]
                
                game_state = {
                    'user_cards': user_cards,
                    'dealer_cards': dealer_cards,
                    'bet': bet,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Сохраняем состояние игры
                c.execute("""INSERT INTO game_states (user_id, game_type, state, timestamp)
                           VALUES (?, 'blackjack', ?, ?)""",
                           (user_id, json.dumps(game_state), datetime.now()))
                
                # Логируем начало игры
                c.execute("""INSERT INTO game_history (user_id, game_type, amount, timestamp)
                           VALUES (?, 'blackjack', ?, ?)""",
                           (user_id, bet, datetime.now()))
                
                user_value = calculate_hand_value(user_cards)
                return f"🃏 Ваши карты: {user_cards} (сумма: {user_value})\n" \
                       f"🎴 Карта дилера: {dealer_cards[0]}\n" \
                       f"Действие? (hit/stand)"
            
            elif action in ['hit', 'stand']:
                # Загружаем состояние игры
                c.execute("""SELECT state FROM game_states 
                           WHERE user_id = ? AND game_type = 'blackjack'
                           ORDER BY timestamp DESC LIMIT 1""", (user_id,))
                saved_state = c.fetchone()
                
                if not saved_state:
                    return "⚠️ Начните новую игру: /blackjack [ставка]"
                
                try:
                    game_state = json.loads(saved_state[0])
                    user_cards = game_state['user_cards']
                    dealer_cards = game_state['dealer_cards']
                    bet = game_state['bet']
                except (json.JSONDecodeError, KeyError) as e:
                    log_error(f"Ошибка при загрузке состояния игры: {str(e)}", exc_info=True)
                    return "❌ Ошибка при загрузке игры. Начните новую: /blackjack [ставка]"
                
                if action == 'hit':
                    # Добавляем карту игроку
                    new_card = random.randint(1, 11)
                    user_cards.append(new_card)
                    user_value = calculate_hand_value(user_cards)
                    
                    if user_value > 21:
                        # Проигрыш
                        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?',
                                (bet, user_id))
                        c.execute('DELETE FROM game_states WHERE user_id = ? AND game_type = ?',
                                (user_id, 'blackjack'))
                        
                        update_user_stats(conn, user_id, -bet)
                        conn.commit()
                        
                        return f"🃏 Ваши карты: {user_cards} (сумма: {user_value})\n" \
                               f"💀 Перебор! Вы проиграли {bet} монет"
                    
                    game_state['user_cards'] = user_cards
                    c.execute("""UPDATE game_states 
                               SET state = ?, timestamp = ?
                               WHERE user_id = ? AND game_type = 'blackjack'""",
                               (json.dumps(game_state), datetime.now(), user_id))
                    
                    return f"🃏 Ваши карты: {user_cards} (сумма: {user_value})\n" \
                           f"🎴 Карта дилера: {dealer_cards[0]}\n" \
                           f"Действие? (hit/stand)"
                
                elif action == 'stand':
                    # Добираем карты дилеру
                    dealer_value = calculate_hand_value(dealer_cards)
                    while dealer_value < 17:
                        dealer_cards.append(random.randint(1, 11))
                        dealer_value = calculate_hand_value(dealer_cards)
                    
                    user_value = calculate_hand_value(user_cards)
                    
                    # Определяем победителя
                    if dealer_value > 21 or user_value > dealer_value:
                        win = bet
                        result = "🎉 Вы победили!"
                    elif user_value < dealer_value:
                        win = -bet
                        result = "😢 Вы проиграли!"
                    else:
                        win = 0
                        result = "🤝 Ничья!"
                    
                    # Обновляем баланс и статистику
                    c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                            (win, user_id))
                    
                    if win != 0:
                        update_user_stats(conn, user_id, win)
                        
                        # Проверяем достижения
                        achievements = check_achievement(conn, user_id, win, 'blackjack')
                        if achievements:
                            result += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
                    
                    # Удаляем состояние игры
                    c.execute('DELETE FROM game_states WHERE user_id = ? AND game_type = ?',
                            (user_id, 'blackjack'))
                    
                    # Логируем результат игры
                    c.execute("""INSERT INTO game_history (user_id, game_type, amount, timestamp)
                               VALUES (?, 'blackjack', ?, ?)""",
                               (user_id, win, datetime.now()))
                    
                    conn.commit()
                    
                    return f"🃏 Ваши карты: {user_cards} (сумма: {user_value})\n" \
                           f"🎴 Карты дилера: {dealer_cards} (сумма: {dealer_value})\n" \
                           f"{result}"
            
            else:
                return "⚠️ Неверное действие. Используйте: hit или stand"
                
        finally:
            conn.close()
            
    except ValueError as e:
        return f"⚠️ {str(e)}"
    except Exception as e:
        log_error(f"Ошибка в blackjack: {str(e)}", exc_info=True)
        return "❌ Произошла ошибка"

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
    """Игра в монетку"""
    if not args:
        return "⚠️ Использование: /flip [сумма] [орел/решка]"
    
    try:
        user_id = event.obj.message['from_id']
        
        # Проверяем формат аргументов
        if len(args) < 2:
            return "⚠️ Укажите ставку и сторону монеты (орел/решка)"
            
        bet = int(args[0])
        choice = args[1].lower()
        
        # Проверяем корректность выбора стороны
        if choice not in ['орел', 'решка']:
            return "⚠️ Выберите: орел или решка"
        
        # Проверяем валидность ставки
        if not validate_bet(bet):
            return "⚠️ Минимальная ставка: 1, максимальная: 1,000,000"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return "❌ Вы не зарегистрированы в системе"
            
        balance = result[0]
        
        if balance < bet:
            conn.close()
            return f"❌ Недостаточно монет! Ваш баланс: {balance}"
        
        # Подбрасываем монетку
        flip_result = 'орел' if random.random() < 0.5 else 'решка'
        
        # Определяем выигрыш
        won = choice == flip_result
        win_amount = bet if won else -bet
        
        # Обновляем баланс
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (win_amount, user_id))
        
        # Обновляем статистику
        if won:
            update_user_stats(conn, user_id, win_amount)
            check_achievement(conn, user_id, win_amount, 'flip')
        
        conn.commit()
        conn.close()
        
        result_emoji = '🦅' if flip_result == 'орел' else '👑'
        result_message = (f"{result_emoji} Выпал {flip_result}!\n"
                         f"{'✅ Вы выиграли' if won else '❌ Вы проиграли'} {abs(win_amount)} монет!")
        
        return result_message
    except ValueError:
        return "❌ Ставка должна быть числом"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_lottery(vk, event, args):
    """Лотерея с накопительным джекпотом"""
    if not args:
        return "⚠️ Укажите количество билетов (1-10)"
    
    try:
        tickets = int(args[0])
        if tickets < 1 or tickets > 10:
            return "⚠️ Можно купить от 1 до 10 билетов"
        
        ticket_price = 100  # Цена одного билета
        total_cost = tickets * ticket_price
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = c.fetchone()
        
        if not balance or balance[0] < total_cost:
            return "❌ Недостаточно монет"
        
        # Получаем текущий джекпот
        c.execute('SELECT value FROM settings WHERE key = "lottery_jackpot"')
        jackpot = c.fetchone()
        if not jackpot:
            c.execute('INSERT INTO settings (key, value) VALUES ("lottery_jackpot", "1000")')
            jackpot = 1000
        else:
            jackpot = int(jackpot[0])
        
        # Генерируем выигрышные числа
        win_numbers = []
        total_win = 0
        
        for _ in range(tickets):
            number = random.randint(1, 100)
            if number <= 5:  # 5% шанс на джекпот
                total_win += jackpot
                win_numbers.append(f"💎 {number} (Джекпот!)")
                # Сбрасываем джекпот
                c.execute('UPDATE settings SET value = "1000" WHERE key = "lottery_jackpot"')
            elif number <= 20:  # 15% шанс на средний выигрыш
                win = ticket_price * 3
                total_win += win
                win_numbers.append(f"🌟 {number} ({win} монет)")
            elif number <= 50:  # 30% шанс на малый выигрыш
                win = ticket_price
                total_win += win
                win_numbers.append(f"⭐ {number} ({win} монет)")
            else:
                win_numbers.append(f"❌ {number}")
        
        # Обновляем баланс и джекпот
        c.execute('UPDATE users SET balance = balance - ? + ? WHERE user_id = ?',
                 (total_cost, total_win, user_id))
        if total_win == 0:
            c.execute('UPDATE settings SET value = value + ? WHERE key = "lottery_jackpot"',
                     (int(total_cost * 0.5),))  # 50% от проигрыша идет в джекпот
        
        # Формируем сообщение
        message = f"🎲 Результаты лотереи:\n"
        message += "\n".join(win_numbers)
        if total_win > 0:
            message += f"\n\n💰 Общий выигрыш: {total_win} монет"
        else:
            message += f"\n\n💸 Нет выигрыша. Потрачено: {total_cost} монет"
        
        # Обновляем статистику
        update_user_stats(conn, user_id, total_win - total_cost)
        
        # Проверяем достижения
        achievements = check_achievement(conn, user_id, total_win)
        if achievements:
            message += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_numbers(vk, event, args):
    """Игра в числа: угадай число от 1 до 100"""
    if len(args) < 2:
        return "⚠️ Использование: /numbers [число] [ставка]"
    
    try:
        number = int(args[0])
        bet = int(args[1])
        
        if number < 1 or number > 100:
            return "⚠️ Загадайте число от 1 до 100"
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
        
        # Генерируем число
        target = random.randint(1, 100)
        
        # Определяем выигрыш
        if number == target:
            win = bet * 50  # Точное попадание
            message = f"🎯 Невероятно! Вы угадали число {target}!\n💰 Выигрыш: {win} монет (x50)"
        elif abs(number - target) <= 5:
            win = bet * 5  # Близкое число (±5)
            message = f"🎯 Почти! Было загадано {target}\n💰 Выигрыш: {win} монет (x5)"
        elif abs(number - target) <= 10:
            win = bet * 2  # Близкое число (±10)
            message = f"🎯 Неплохо! Было загадано {target}\n💰 Выигрыш: {win} монет (x2)"
        else:
            win = -bet
            message = f"🎯 Не угадали! Было загадано {target}\n💸 Проигрыш: {bet} монет"
        
        # Обновляем баланс и статистику
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (win, user_id))
        update_user_stats(conn, user_id, win)
        
        # Проверяем достижения
        achievements = check_achievement(conn, user_id, win)
        if achievements:
            message += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_jackpot(vk, event, args):
    """Игра Jackpot - общий банк, один победитель"""
    if not args:
        return "⚠️ Укажите ставку"
    
    try:
        bet = int(args[0])
        if bet < 100:
            return "⚠️ Минимальная ставка: 100 монет"
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = c.fetchone()
        
        if not balance or balance[0] < bet:
            return "❌ Недостаточно монет"
        
        # Получаем текущий банк
        c.execute('SELECT value FROM settings WHERE key = "jackpot_bank"')
        current_bank = c.fetchone()
        if not current_bank:
            c.execute('INSERT INTO settings (key, value) VALUES ("jackpot_bank", "0")')
            current_bank = 0
        else:
            current_bank = int(current_bank[0])
        
        # Добавляем ставку в банк
        new_bank = current_bank + bet
        c.execute('UPDATE settings SET value = ? WHERE key = "jackpot_bank"', (str(new_bank),))
        
        # Списываем ставку
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (bet, user_id))
        
        # Шанс на выигрыш зависит от размера ставки
        win_chance = bet / new_bank
        
        if random.random() < win_chance:
            # Победа
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (new_bank, user_id))
            c.execute('UPDATE settings SET value = "0" WHERE key = "jackpot_bank"')
            message = f"🎉 Поздравляем! Вы сорвали джекпот!\n💰 Выигрыш: {new_bank} монет"
            update_user_stats(conn, user_id, new_bank)
            
            # Проверяем достижения
            achievements = check_achievement(conn, user_id, new_bank)
            if achievements:
                message += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
        else:
            message = f"😢 Не повезло!\n💰 Текущий банк: {new_bank} монет\n🎲 Ваш шанс был: {win_chance*100:.1f}%"
            update_user_stats(conn, user_id, -bet)
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_poker(vk, event, args):
    """Упрощенная версия покера"""
    if not args:
        return "⚠️ Укажите ставку"
    
    try:
        bet = int(args[0])
        if bet < 50:
            return "⚠️ Минимальная ставка: 50 монет"
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = c.fetchone()
        
        if not balance or balance[0] < bet:
            return "❌ Недостаточно монет"
        
        # Карты и их значения
        cards = ['2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟', '🇯', '🇶', '🇰', '🇦']
        suits = ['♠️', '♥️', '♦️', '♣️']
        
        # Раздаем карты
        player_cards = []
        dealer_cards = []
        deck = [(card, suit) for card in cards for suit in suits]
        random.shuffle(deck)
        
        for _ in range(5):
            player_cards.append(deck.pop())
            dealer_cards.append(deck.pop())
        
        # Оцениваем комбинации
        def evaluate_hand(hand):
            values = [cards.index(card[0]) for card in hand]
            suits_in_hand = [card[1] for card in hand]
            
            # Флеш
            flush = len(set(suits_in_hand)) == 1
            
            # Стрит
            values.sort()
            straight = all(values[i+1] - values[i] == 1 for i in range(len(values)-1))
            
            # Пары и сеты
            value_counts = {values.count(v): v for v in set(values)}
            
            if flush and straight:
                return 8, max(values)  # Стрит-флеш
            elif 4 in value_counts:
                return 7, value_counts[4]  # Каре
            elif 3 in value_counts and 2 in value_counts:
                return 6, value_counts[3]  # Фулл-хаус
            elif flush:
                return 5, max(values)  # Флеш
            elif straight:
                return 4, max(values)  # Стрит
            elif 3 in value_counts:
                return 3, value_counts[3]  # Тройка
            elif list(value_counts.keys()).count(2) == 2:
                return 2, max(v for k, v in value_counts.items() if k == 2)  # Две пары
            elif 2 in value_counts:
                return 1, value_counts[2]  # Пара
            else:
                return 0, max(values)  # Старшая карта
        
        player_score = evaluate_hand(player_cards)
        dealer_score = evaluate_hand(dealer_cards)
        
        # Форматируем карты для вывода
        def format_cards(cards):
            return ' '.join(f"{card[0]}{card[1]}" for card in cards)
        
        # Определяем победителя
        if player_score > dealer_score:
            win = bet * 2
            result = "🎉 Вы победили!"
        elif player_score < dealer_score:
            win = -bet
            result = "😢 Вы проиграли!"
        else:
            win = 0
            result = "🤝 Ничья!"
        
        # Обновляем баланс
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (win, user_id))
        update_user_stats(conn, user_id, win)
        
        message = (f"🃏 Ваши карты: {format_cards(player_cards)}\n"
                  f"🎴 Карты дилера: {format_cards(dealer_cards)}\n"
                  f"{result}")
        
        if win != 0:
            achievements = check_achievement(conn, user_id, win)
            if achievements:
                message += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_tournament(vk, event):
    """Ежедневный турнир по играм"""
    try:
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем, идет ли сейчас турнир
        c.execute('SELECT value FROM settings WHERE key = "tournament_end"')
        tournament_end = c.fetchone()
        
        current_time = datetime.now()
        
        if not tournament_end:
            # Создаем новый турнир
            tournament_end = current_time + timedelta(days=1)
            c.execute('INSERT INTO settings (key, value) VALUES ("tournament_end", ?)',
                     (tournament_end.strftime('%Y-%m-%d %H:%M:%S'),))
            c.execute('DELETE FROM settings WHERE key = "tournament_players"')
            message = "🎮 Начался новый турнир!\n"
        else:
            tournament_end = datetime.strptime(tournament_end[0], '%Y-%m-%d %H:%M:%S')
            if current_time > tournament_end:
                # Подводим итоги турнира
                c.execute('SELECT value FROM settings WHERE key = "tournament_players"')
                players = c.fetchone()
                if players:
                    players = eval(players[0])  # Безопасно, так как мы сами сохраняли
                    
                    # Сортируем игроков по выигрышу
                    sorted_players = sorted(players.items(), key=lambda x: x[1], reverse=True)
                    
                    # Награждаем победителей
                    rewards = {0: 10000, 1: 5000, 2: 2500}  # Награды за места
                    message = "🏆 Итоги турнира:\n\n"
                    
                    for i, (player_id, score) in enumerate(sorted_players[:3]):
                        reward = rewards.get(i, 0)
                        if reward:
                            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                                    (reward, int(player_id)))
                            user_info = vk.users.get(user_ids=[player_id])[0]
                            message += f"{i+1}. @id{player_id} ({user_info['first_name']})"
                            message += f" — {score} очков, награда: {reward} монет\n"
                    
                    # Начинаем новый турнир
                    tournament_end = current_time + timedelta(days=1)
                    c.execute('UPDATE settings SET value = ? WHERE key = "tournament_end"',
                             (tournament_end.strftime('%Y-%m-%d %H:%M:%S'),))
                    c.execute('DELETE FROM settings WHERE key = "tournament_players"')
                else:
                    message = "😢 В турнире никто не участвовал\n"
            else:
                # Показываем текущий статус турнира
                c.execute('SELECT value FROM settings WHERE key = "tournament_players"')
                players = c.fetchone()
                players = eval(players[0]) if players else {}
                
                message = "🎮 Текущий статус турнира:\n\n"
                sorted_players = sorted(players.items(), key=lambda x: x[1], reverse=True)
                
                for i, (player_id, score) in enumerate(sorted_players[:5]):
                    user_info = vk.users.get(user_ids=[player_id])[0]
                    message += f"{i+1}. @id{player_id} ({user_info['first_name']}) — {score} очков\n"
                
                message += f"\n⏳ До конца турнира: {str(tournament_end - current_time).split('.')[0]}"
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def validate_bet(bet, min_bet=1, max_bet=1000000):
    """Проверка корректности ставки"""
    if not isinstance(bet, int):
        raise ValueError("Ставка должна быть целым числом")
    if bet < min_bet:
        raise ValueError(f"Минимальная ставка: {min_bet} монет")
    if bet > max_bet:
        raise ValueError(f"Максимальная ставка: {max_bet} монет")
    return True

def cmd_baccarat(vk, event, args):
    """Игра в баккара"""
    if not args:
        return "⚠️ Использование: /baccarat [ставка] [player/banker/tie]"
    
    try:
        bet = int(args[0])
        bet_type = args[1].lower() if len(args) > 1 else 'player'
        
        if bet_type not in ['player', 'banker', 'tie']:
            return "⚠️ Выберите ставку: player, banker или tie"
        
        # Валидация ставки
        validate_bet(bet, min_bet=100, max_bet=100000)
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем баланс
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = c.fetchone()
        
        if not balance or balance[0] < bet:
            return "❌ Недостаточно монет"
        
        # Раздаем карты
        def draw_card():
            return random.randint(1, 10)  # 10 включает также J, Q, K
        
        player = [draw_card(), draw_card()]
        banker = [draw_card(), draw_card()]
        
        # Правила третьей карты
        player_score = sum(player) % 10
        banker_score = sum(banker) % 10
        
        if player_score <= 5:
            player.append(draw_card())
            player_score = sum(player) % 10
        
        if banker_score <= 5 and (len(player) == 2 or banker_score < player_score):
            banker.append(draw_card())
            banker_score = sum(banker) % 10
        
        # Определяем победителя
        if player_score > banker_score:
            winner = 'player'
        elif banker_score > player_score:
            winner = 'banker'
        else:
            winner = 'tie'
        
        # Рассчитываем выигрыш
        multipliers = {'player': 2, 'banker': 1.95, 'tie': 9}
        
        if winner == bet_type:
            win = int(bet * multipliers[bet_type])
            result = "🎉 Вы победили!"
        else:
            win = -bet
            result = "😢 Вы проиграли!"
        
        # Обновляем баланс и статистику
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                 (win, user_id))
        update_user_stats(conn, user_id, win)
        
        message = (f"🎴 Карты игрока: {player} (сумма: {player_score})\n"
                  f"🎴 Карты банкира: {banker} (сумма: {banker_score})\n"
                  f"{result}")
        
        if win > 0:
            achievements = check_achievement(conn, user_id, win, 'baccarat')
            if achievements:
                message += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_crash(vk, event, args):
    """Игра Crash - растущий множитель, нужно успеть забрать выигрыш"""
    if not args:
        return "⚠️ Использование: /crash [ставка] [действие: start/cashout]"
    
    try:
        bet = int(args[0])
        action = args[1].lower() if len(args) > 1 else 'start'
        
        # Валидация ставки
        validate_bet(bet, min_bet=50, max_bet=50000)
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        if action == 'start':
            # Проверяем баланс
            c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            balance = c.fetchone()
            
            if not balance or balance[0] < bet:
                return "❌ Недостаточно монет"
            
            # Генерируем точку краха (1.0 - 10.0)
            crash_point = round(random.uniform(1.0, 10.0), 2)
            
            # Сохраняем состояние игры
            game_state = {
                'bet': bet,
                'crash_point': crash_point,
                'current_multiplier': 1.0,
                'timestamp': datetime.now().isoformat()
            }
            
            c.execute("""INSERT INTO game_states (user_id, game_type, state, timestamp)
                       VALUES (?, 'crash', ?, ?)""",
                       (user_id, json.dumps(game_state), datetime.now()))
            
            # Списываем ставку
            c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?',
                     (bet, user_id))
            
            conn.commit()
            return f"📈 Игра началась!\nСтавка: {bet} монет\nТекущий множитель: 1.00x\nИспользуйте /crash [ставка] cashout чтобы забрать выигрыш"
            
        elif action == 'cashout':
            # Загружаем состояние игры
            c.execute("""SELECT state FROM game_states 
                       WHERE user_id = ? AND game_type = 'crash'
                       ORDER BY timestamp DESC LIMIT 1""", (user_id,))
            saved_state = c.fetchone()
            
            if not saved_state:
                return "⚠️ Нет активной игры"
            
            game_state = json.loads(saved_state[0])
            crash_point = game_state['crash_point']
            current_multiplier = round(game_state['current_multiplier'] + 0.1, 2)
            
            if current_multiplier >= crash_point:
                # Игра окончена - проигрыш
                c.execute('DELETE FROM game_states WHERE user_id = ? AND game_type = ?',
                         (user_id, 'crash'))
                conn.commit()
                return f"💥 Крах при {crash_point}x!\nВы потеряли {bet} монет"
            
            # Успешный вывод
            win = int(bet * current_multiplier)
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                     (win, user_id))
            update_user_stats(conn, user_id, win - bet)
            
            # Удаляем состояние игры
            c.execute('DELETE FROM game_states WHERE user_id = ? AND game_type = ?',
                     (user_id, 'crash'))
            
            message = f"✅ Успешный вывод при {current_multiplier}x!\n💰 Выигрыш: {win} монет"
            
            achievements = check_achievement(conn, user_id, win - bet, 'crash')
            if achievements:
                message += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
            
            conn.commit()
            return message
            
        else:
            return "⚠️ Неверное действие. Используйте: start или cashout"
            
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_mines(vk, event, args):
    """Игра Mines - выбирайте клетки и не попадите на мину"""
    if not args:
        return "⚠️ Использование: /mines [ставка] [действие: start/open X/cashout]"
    
    try:
        bet = int(args[0])
        action = args[1].lower() if len(args) > 1 else 'start'
        
        # Валидация ставки
        validate_bet(bet, min_bet=50, max_bet=50000)
        
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        if action == 'start':
            # Проверяем баланс
            c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            balance = c.fetchone()
            
            if not balance or balance[0] < bet:
                return "❌ Недостаточно монет"
            
            # Создаем поле 5x5 с 5 минами
            field = ['💎'] * 25
            mines = random.sample(range(25), 5)
            for mine in mines:
                field[mine] = '💣'
            
            # Сохраняем состояние игры
            game_state = {
                'bet': bet,
                'field': field,
                'opened': [],
                'multiplier': 1.0,
                'timestamp': datetime.now().isoformat()
            }
            
            c.execute("""INSERT INTO game_states (user_id, game_type, state, timestamp)
                       VALUES (?, 'mines', ?, ?)""",
                       (user_id, json.dumps(game_state), datetime.now()))
            
            # Списываем ставку
            c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?',
                     (bet, user_id))
            
            # Формируем отображение поля
            display = ['❓'] * 25
            field_display = '\n'.join(' '.join(display[i:i+5]) for i in range(0, 25, 5))
            
            conn.commit()
            return f"💎 Игра началась!\nСтавка: {bet} монет\nМножитель: 1.00x\n\n{field_display}\n\nИспользуйте /mines [ставка] open [1-25] чтобы открыть клетку"
            
        elif action.startswith('open'):
            try:
                position = int(args[2]) - 1
                if position < 0 or position >= 25:
                    return "⚠️ Выберите клетку от 1 до 25"
            except:
                return "⚠️ Укажите номер клетки"
            
            # Загружаем состояние игры
            c.execute("""SELECT state FROM game_states 
                       WHERE user_id = ? AND game_type = 'mines'
                       ORDER BY timestamp DESC LIMIT 1""", (user_id,))
            saved_state = c.fetchone()
            
            if not saved_state:
                return "⚠️ Нет активной игры"
            
            game_state = json.loads(saved_state[0])
            field = game_state['field']
            opened = game_state['opened']
            
            if position in opened:
                return "⚠️ Эта клетка уже открыта"
            
            if field[position] == '💣':
                # Игра окончена - проигрыш
                c.execute('DELETE FROM game_states WHERE user_id = ? AND game_type = ?',
                         (user_id, 'mines'))
                
                # Показываем все мины
                display = ['❓'] * 25
                for i, cell in enumerate(field):
                    if cell == '💣' or i in opened:
                        display[i] = cell
                field_display = '\n'.join(' '.join(display[i:i+5]) for i in range(0, 25, 5))
                
                conn.commit()
                return f"💥 Бум! Вы попали на мину!\nВы потеряли {bet} монет\n\n{field_display}"
            
            # Успешное открытие клетки
            opened.append(position)
            game_state['opened'] = opened
            game_state['multiplier'] = round(1.0 + len(opened) * 0.2, 2)
            
            # Обновляем состояние игры
            c.execute("""UPDATE game_states 
                       SET state = ?, timestamp = ?
                       WHERE user_id = ? AND game_type = 'mines'""",
                       (json.dumps(game_state), datetime.now(), user_id))
            
            # Показываем текущее поле
            display = ['❓'] * 25
            for i in opened:
                display[i] = field[i]
            field_display = '\n'.join(' '.join(display[i:i+5]) for i in range(0, 25, 5))
            
            conn.commit()
            return f"💎 Успешно! Множитель: {game_state['multiplier']}x\n\n{field_display}\n\nПродолжайте открывать клетки или используйте /mines [ставка] cashout чтобы забрать выигрыш"
            
        elif action == 'cashout':
            # Загружаем состояние игры
            c.execute("""SELECT state FROM game_states 
                       WHERE user_id = ? AND game_type = 'mines'
                       ORDER BY timestamp DESC LIMIT 1""", (user_id,))
            saved_state = c.fetchone()
            
            if not saved_state:
                return "⚠️ Нет активной игры"
            
            game_state = json.loads(saved_state[0])
            win = int(bet * game_state['multiplier'])
            
            # Обновляем баланс и статистику
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                     (win, user_id))
            update_user_stats(conn, user_id, win - bet)
            
            # Удаляем состояние игры
            c.execute('DELETE FROM game_states WHERE user_id = ? AND game_type = ?',
                     (user_id, 'mines'))
            
            message = f"✅ Успешный вывод!\n💰 Выигрыш: {win} монет (x{game_state['multiplier']})"
            
            achievements = check_achievement(conn, user_id, win - bet, 'mines')
            if achievements:
                message += "\n🏆 Получены достижения:\n" + "\n".join(achievements)
            
            conn.commit()
            return message
            
        else:
            return "⚠️ Неверное действие. Используйте: start, open или cashout"
            
    except Exception as e:
        return f"❌ Ошибка: {str(e)}" 