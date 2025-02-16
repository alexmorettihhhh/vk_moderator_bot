import os
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sqlite3
import json
import threading
from fun_commands import (
    cmd_profile, cmd_daily, cmd_marry, cmd_divorce,
    cmd_rep, cmd_game, cmd_top, cmd_nickname, cmd_achievements,
    cmd_give
)
from games import (
    cmd_slots, cmd_duel, cmd_wheel, cmd_flip, cmd_dice,
    cmd_russian_roulette, cmd_blackjack, cmd_lottery, cmd_numbers,
    cmd_jackpot, cmd_poker, cmd_tournament, cmd_baccarat,
    cmd_crash, cmd_mines
)
from utils import get_weather, get_currency_rates, extract_user_id, get_vk_reg_date
from admin_commands import (
    cmd_skick, cmd_quiet, cmd_sban, cmd_sunban,
    cmd_addsenmoder, cmd_bug, cmd_stats_chat, cmd_settings,
    cmd_addadmin, cmd_removeadmin, cmd_massban, cmd_unbanall,
    cmd_clear_warns, cmd_reset_stats, cmd_admin_list, cmd_givemoney
)
from moderator_commands import (
    cmd_mute, cmd_unmute, cmd_warn, cmd_unwarn,
    cmd_getban, cmd_getwarn, cmd_warnhistory, cmd_staff
)
from senior_moderator_commands import (
    cmd_ban, cmd_unban, cmd_addmoder, cmd_removerole,
    cmd_zov, cmd_online, cmd_banlist, cmd_onlinelist
)
from logger import setup_logger, setup_command_logger, log_command, log_error
from backup import create_backup
from antispam import antispam
from cleanup import schedule_cleanup
from db_update import update_database, adapt_datetime, convert_datetime
import time
import sys
from requests.exceptions import ConnectionError, ReadTimeout
from image_generator import generate_stats_image
from admin_utils import (
    cmd_filter, cmd_pin, cmd_export,
    cmd_welcome, cmd_backup, cmd_automod
)

# Инициализация логгеров
logger = setup_logger()
cmd_logger = setup_command_logger()

# Load environment variables
load_dotenv()

# VK Bot configuration
TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))

# Initialize SQLite adapters
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("TIMESTAMP", convert_datetime)

# Initialize VK session
def init_vk():
    """Инициализация VK сессии"""
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    return vk_session, vk, longpoll

# Database initialization
def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Создаем необходимые таблицы
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (user_id INTEGER PRIMARY KEY,
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
                     last_activity TIMESTAMP)''')

        c.execute('''CREATE TABLE IF NOT EXISTS marriages
                    (user1_id INTEGER,
                     user2_id INTEGER,
                     marriage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     FOREIGN KEY (user1_id) REFERENCES users(user_id),
                     FOREIGN KEY (user2_id) REFERENCES users(user_id),
                     PRIMARY KEY (user1_id, user2_id))''')

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

        c.execute('''CREATE TABLE IF NOT EXISTS chat_settings
                    (chat_id INTEGER PRIMARY KEY,
                     quiet_mode INTEGER DEFAULT 0,
                     quiet_end TIMESTAMP,
                     welcome_message TEXT,
                     auto_warn INTEGER DEFAULT 0,
                     max_warnings INTEGER DEFAULT 3)''')

        c.execute('''CREATE TABLE IF NOT EXISTS bot_chats
                    (chat_id INTEGER PRIMARY KEY,
                     join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     is_active INTEGER DEFAULT 1)''')
                     
        # Проверяем количество пользователей
        c.execute('SELECT COUNT(*) FROM users')
        user_count = c.fetchone()[0]
        
        # Если база пуста, следующий пользователь будет админом
        if user_count == 0:
            logger.info("База данных пуста. Следующий пользователь будет назначен администратором.")
            c.execute('INSERT OR REPLACE INTO users (user_id, role, reg_date) VALUES (?, ?, ?)', 
                     (694099447, 'admin', datetime.now()))
        
        # Добавляем колонку reg_date, если её нет
        try:
            c.execute('ALTER TABLE users ADD COLUMN reg_date TIMESTAMP')
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
            
        # Добавляем колонку invited_count, если её нет
        try:
            c.execute('ALTER TABLE users ADD COLUMN invited_count INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
        return False

# User commands
def cmd_info(vk, event):
    return "📚 Официальные ресурсы проекта:\n• Группа ВК: vk.com/group\n• Сайт: example.com"

def cmd_stats(vk, event):
    """Показать статистику пользователя с изображением"""
    try:
        user_id = event.obj.message['from_id']
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Подсчитываем количество сообщений для пользователя
        c.execute('''SELECT COUNT(*) FROM message_history WHERE user_id = ?''', (user_id,))
        messages_count = c.fetchone()[0]
        
        # Обновляем количество сообщений в таблице users
        c.execute('''UPDATE users SET messages_count = ? WHERE user_id = ?''', (messages_count, user_id))
        conn.commit()
        
        # Получаем информацию о пользователе
        c.execute('''SELECT level, xp, balance, reputation, role, reg_date, invited_count
                    FROM users 
                    WHERE user_id = ?''', (user_id,))
        result = c.fetchone()
        
        if not result:
            return "❌ Пользователь не найден в базе данных"
            
        level, xp, balance, reputation, role, reg_date, invited_count = result
        
        # Получаем информацию о пользователе из VK API
        user_info = vk.users.get(user_ids=[user_id], fields=['photo_max_orig'])[0]
        
        # Формируем данные для изображения
        user_data = {
            'user_id': user_id,
            'level': level,
            'xp': xp,
            'balance': balance,
            'reputation': reputation,
            'role': role,
            'messages': messages_count,
            'reg_date': reg_date,
            'invited_count': invited_count,
            'avatar_url': user_info.get('photo_max_orig')
        }
        
        # Генерируем изображение
        image_path = generate_stats_image(user_data)
        if not image_path:
            return "❌ Ошибка при создании изображения"
            
        # Загружаем изображение
        upload = vk_api.VkUpload(vk)
        photo = upload.photo_messages(image_path)[0]
        
        # Формируем attachment
        attachment = f"photo{photo['owner_id']}_{photo['id']}"
        
        # Отправляем сообщение с изображением
        vk.messages.send(
            peer_id=event.obj.message['peer_id'],
            attachment=attachment,
            random_id=get_random_id()
        )
        
        # Удаляем временный файл
        try:
            os.remove(image_path)
        except:
            pass
            
        return None
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_getid(vk, event):
    user_id = event.obj.message['from_id']
    return f"🆔 Ваш ID: {user_id}"

def cmd_help(vk, event, args):
    """Показать список доступных команд"""
    try:
        user_id = event.obj.message['from_id']
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        # Получаем роль пользователя
        c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
        role = c.fetchone()
        role = role[0] if role else 'user'
        conn.close()
        
        message = "📚 Доступные команды:\n\n"
        message += "👤 Команды пользователя:\n"
        message += "• /info — официальные ресурсы проекта\n"
        message += "• /stats — информация о пользователе\n"
        message += "• /getid — узнать свой ID\n"
        message += "• /profile [ID] — просмотр профиля\n"
        message += "• /daily — ежедневная награда\n"
        message += "• /marry [ID] — заключить брак\n"
        message += "• /divorce — развестись\n"
        message += "• /rep [ID] [причина] — повысить репутацию\n"
        message += "• /game [камень/ножницы/бумага] — игра\n"
        message += "• /top [level/messages/balance/rep] — топ игроков\n"
        message += "• /give [ID] [количество] — передать монеты\n"
        message += "• /nickname [ник] — установить ник\n"
        message += "• /nlist — список пользователей с никами\n"
        message += "• /achievements — посмотреть свои достижения\n\n"
        
        message += "🎮 Игровые команды:\n"
        message += "• /slots [ставка] — игровые автоматы\n"
        message += "• /duel [ID] [ставка] — дуэль\n"
        message += "• /wheel [ставка] [red/black/green] — рулетка\n"
        message += "• /flip [ставка] [heads/tails] — монетка\n"
        message += "• /dice [ставка] — кости\n"
        message += "• /roulette — русская рулетка\n"
        message += "• /blackjack [ставка] — блэкджек\n"
        message += "• /lottery [кол-во билетов] — лотерея\n"
        message += "• /numbers [число] [ставка] — угадай число\n\n"
        
        message += "🛠 Утилиты:\n"
        message += "• /weather [город] — погода\n"
        message += "• /rates — курсы валют\n"
        
        if role in ['moderator', 'senior_moderator', 'admin']:
            message += "\n👮 Команды модератора:\n"
            message += "• /kick [ID] — кик пользователя\n"
            message += "• /mute [ID] [время] [причина] — мут\n"
            message += "• /unmute [ID] — размут\n"
            message += "• /warn [ID] [причина] — варн\n"
            message += "• /unwarn [ID] — снять варн\n"
            message += "• /getban [ID] — инфо о банах\n"
            message += "• /getwarn [ID] — инфо о варнах\n"
            message += "• /warnhistory [ID] — история варнов\n"
            message += "• /staff — список персонала\n"
        
        if role in ['senior_moderator', 'admin']:
            message += "\n🔨 Команды старшего модератора:\n"
            message += "• /ban [ID] [причина] — бан\n"
            message += "• /unban [ID] — разбан\n"
            message += "• /addmoder [ID] — назначить модератора\n"
            message += "• /removerole [ID] — снять роль\n"
            message += "• /zov — призвать всех\n"
            message += "• /online — список онлайн\n"
            message += "• /banlist — список банов\n"
            message += "• /onlinelist — подробный онлайн\n"
        
        if role == 'admin':
            message += "\n👑 Команды администратора:\n"
            message += "• /skick [ID] [причина] — кик со всех бесед\n"
            message += "• /quiet [время] — режим тишины\n"
            message += "• /sban [ID] [причина] — бан во всех беседах\n"
            message += "• /sunban [ID] — разбан во всех беседах\n"
            message += "• /addsenmoder [ID] — назначить ст.модера\n"
            message += "• /addadmin [ID] — назначить администратора\n"
            message += "• /removeadmin [ID] — снять администратора\n"
            message += "• /massban [ID1] [ID2] ... [причина] — массовый бан\n"
            message += "• /unbanall — разбанить всех в беседе\n"
            message += "• /clearwarns [ID] — очистить все предупреждения\n"
            message += "• /resetstats [ID] — сбросить статистику\n"
            message += "• /adminlist — список администраторов\n"
            message += "• /bug [описание] — сообщить о баге\n"
            message += "• /settings [параметр] [значение] — настройки беседы\n"
            message += "• /snick [ID] [ник] — установить ник пользователю\n"
            message += "• /givemoney [ID] [количество] — выдать монеты пользователю\n"
            message += "\n⚙️ Управление беседой:\n"
            message += "• /filter [add/remove/list] [слово] — управление фильтром слов\n"
            message += "• /pin — закрепить сообщение (ответом)\n"
            message += "• /export — экспорт данных беседы\n"
            message += "• /welcome [set/clear/show] — управление приветствием\n"
            message += "• /backup [create/list/restore] — управление резервными копиями\n"
            message += "• /automod [status/spam/caps/links/warns/action] — настройка автомодерации\n"
        
        return message
    except Exception as e:
        log_error(f"Ошибка в команде help: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

# Moderator commands
def cmd_kick(vk, event, args):
    if not is_moderator(event.obj.message['from_id']):
        return "⚠️ У вас нет прав для использования этой команды"
    
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        vk.messages.removeChatUser(
            chat_id=event.chat_id,
            user_id=user_id
        )
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ Пользователь @id{user_id} ({user_info['first_name']}) исключен из беседы"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def is_moderator(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] in ['moderator', 'senior_moderator', 'admin']

def is_senior_moderator(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] in ['senior_moderator', 'admin']

def is_admin(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 'admin'

# Add XP and check level up
def add_xp(vk, event, user_id, xp_amount):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    # Get current XP and level
    c.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    if result:
        current_xp, current_level = result
        new_xp = current_xp + xp_amount
        
        # Calculate new level (each level requires level * 1000 XP)
        new_level = current_level
        while new_xp >= new_level * 1000:
            new_xp -= new_level * 1000
            new_level += 1
        
        # Update user data
        c.execute('''UPDATE users 
                    SET xp = ?, level = ?
                    WHERE user_id = ?''', (new_xp, new_level, user_id))
        
        conn.commit()
        conn.close()
        
        return new_level > current_level
    else:
        # Create new user entry and check if this is the first user
        c.execute('SELECT COUNT(*) FROM users')
        user_count = c.fetchone()[0]
        
        # If this is the first user, make them admin
        role = 'admin' if user_count == 0 else 'user'
        
        c.execute('''INSERT INTO users (user_id, xp, level, role) 
                    VALUES (?, ?, 1, ?)''', (user_id, xp_amount, role))
        
        conn.commit()
        
        if role == 'admin':
            vk.messages.send(
                chat_id=event.chat_id,
                message=f"👑 @id{user_id}, вы назначены администратором бота как первый пользователь!",
                random_id=get_random_id()
            )
        
        conn.close()
        return False

def get_user_role(user_id):
    """Получить роль пользователя"""
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 'user'

def is_quiet_mode(chat_id):
    """Проверяет, включен ли режим тишины в чате"""
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''SELECT quiet_mode, quiet_end 
                    FROM chat_settings 
                    WHERE chat_id = ?''', (chat_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            quiet_mode, quiet_end = result
            if quiet_mode:
                if quiet_end:
                    quiet_end = datetime.strptime(quiet_end, '%Y-%m-%d %H:%M:%S.%f')
                    if quiet_end > datetime.now():
                        return True
                    else:
                        # Автоматически выключаем режим тишины по истечении времени
                        conn = sqlite3.connect('bot.db')
                        c = conn.cursor()
                        c.execute('''UPDATE chat_settings 
                                   SET quiet_mode = 0, quiet_end = NULL 
                                   WHERE chat_id = ?''', (chat_id,))
                        conn.commit()
                        conn.close()
                        return False
                return True
        return False
    except Exception:
        return False

def cmd_snick(vk, event, args):
    """Установка ника другому пользователю (только для администраторов)"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args or len(args) < 2:
        return "⚠️ Использование: /snick [ID] [ник]"
    
    try:
        target = args[0]
        nickname = ' '.join(args[1:])
        
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
            
        if len(nickname) > 20:
            return "⚠️ Максимальная длина ника: 20 символов"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Обновляем ник
        c.execute('UPDATE users SET nickname = ? WHERE user_id = ?', (nickname, user_id))
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"🏷 Установлен ник для @id{user_id} ({user_info['first_name']}): {nickname}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_nlist(vk, event):
    """Показать список пользователей с их никами"""
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем всех пользователей с никами
        c.execute('''SELECT user_id, nickname 
                    FROM users 
                    WHERE nickname IS NOT NULL 
                    ORDER BY nickname''')
        users = c.fetchall()
        conn.close()
        
        if not users:
            return "📋 Нет пользователей с установленными никами"
        
        # Получаем информацию о пользователях через VK API
        user_ids = [user[0] for user in users]
        users_info = vk.users.get(user_ids=user_ids)
        users_dict = {user['id']: user for user in users_info}
        
        message = "📋 Список пользователей с никами:\n\n"
        for user_id, nickname in users:
            user = users_dict.get(user_id, {'first_name': 'Unknown', 'last_name': 'User'})
            message += f"• @id{user_id} ({user['first_name']} {user['last_name']}) — {nickname}\n"
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_music(vk, event, args):
    """Ищет музыку в VK и отправляет в чат"""
    if not args:
        return "⚠️ Укажите название песни или исполнителя"
    
    query = ' '.join(args)
    try:
        # Используем метод audio.search для поиска музыки
        response = vk.audio.search(q=query, count=1)
        if response['count'] > 0:
            audio = response['items'][0]
            artist = audio['artist']
            title = audio['title']
            url = audio['url']
            return f"🎵 {artist} - {title}\n{url}"
        else:
            return "❌ Музыка не найдена"
    except Exception as e:
        return f"❌ Ошибка при поиске музыки: {str(e)}"

def main():
    """Основная функция бота"""
    try:
        # Инициализация базы данных
        init_db()
        
        # Обновление структуры базы данных
        if not update_database():
            logger.error("Не удалось обновить структуру базы данных")
            return
        
        # Инициализация VK
        vk_session, vk, longpoll = init_vk()
        
        # Запуск фоновых задач
        cleanup_thread = threading.Thread(target=schedule_cleanup, daemon=True)
        cleanup_thread.start()
        
        # Создаем бэкап при запуске
        if create_backup():
            logger.info("Создан бэкап базы данных при запуске")
        else:
            logger.warning("Не удалось создать бэкап базы данных при запуске")
        
        logger.info("Бот запущен и готов к работе")
        
        # Основной цикл
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW and event.from_chat:
                # Получаем информацию о сообщении
                message = event.obj.message
                user_id = message['from_id']
                chat_id = event.chat_id
                text = message['text'].lower()
                
                try:
                    # Проверяем, является ли это событием приглашения пользователя
                    if 'action' in message and message['action']['type'] == 'chat_invite_user':
                        invited_user_id = message['action']['member_id']
                        # Не обновляем счетчик, если пользователь сам вернулся в беседу
                        if invited_user_id != user_id:
                            conn = sqlite3.connect('bot.db')
                            c = conn.cursor()
                            c.execute('''UPDATE users 
                                       SET invited_count = invited_count + 1 
                                       WHERE user_id = ?''', (user_id,))
                            conn.commit()
                            conn.close()
                        continue

                    # Проверка на спам
                    is_spam, spam_reason = antispam.is_message_spam(user_id, text)
                    if is_spam:
                        spam_message = antispam.handle_spam(vk, chat_id, user_id, spam_reason)
                        if spam_message:
                            vk.messages.send(
                                chat_id=chat_id,
                                message=spam_message,
                                random_id=get_random_id()
                            )
                        continue
                    
                    # Открываем одно соединение для всех операций с базой данных
                    conn = sqlite3.connect('bot.db')
                    c = conn.cursor()
                    
                    try:
                        # Проверяем существование пользователя
                        c.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
                        if not c.fetchone():
                            c.execute('''INSERT INTO users 
                                        (user_id, messages_count, reg_date) 
                                        VALUES (?, 0, ?)''', 
                                        (user_id, datetime.now()))
                        
                        # Проверяем, не было ли такого сообщения в последние 5 секунд
                        five_seconds_ago = datetime.now() - timedelta(seconds=5)
                        c.execute('''SELECT 1 FROM message_history 
                                    WHERE user_id = ? AND chat_id = ? 
                                    AND timestamp > ?''', 
                                    (user_id, chat_id, five_seconds_ago))
                        
                        if not c.fetchone():
                            # Добавляем сообщение в историю
                            current_time = datetime.now()
                            c.execute('''INSERT INTO message_history 
                                        (user_id, chat_id, message_type, timestamp)
                                        VALUES (?, ?, ?, ?)''', 
                                        (user_id, chat_id, 'text', current_time))
                            
                            # Обновляем время последней активности
                            c.execute('''UPDATE users 
                                        SET last_activity = ? 
                                        WHERE user_id = ?''', 
                                        (current_time, user_id))
                        
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        logger.error(f"Ошибка при обработке сообщения: {str(e)}", exc_info=True)
                    finally:
                        conn.close()
                    
                    # Логируем команду, если это команда
                    if text.startswith('/'):
                        command = text.split()[0][1:]
                        args = text.split()[1:] if len(text.split()) > 1 else []
                        log_command(user_id, chat_id, command, args)
                    
                    # Проверяем режим тишины и права пользователя
                    if is_quiet_mode(chat_id):
                        user_role = get_user_role(user_id)
                        if user_role not in ['admin', 'senior_moderator', 'moderator']:
                            # Удаляем сообщение от обычного пользователя
                            try:
                                vk.messages.delete(
                                    peer_id=2000000000 + chat_id,
                                    conversation_message_ids=[event.obj.message['conversation_message_id']],
                                    delete_for_all=1
                                )
                                continue
                            except:
                                pass
                    
                    # Add XP for message (if not a command)
                    if not text.startswith('/'):
                        if add_xp(vk, event, user_id, 10):  # Pass event object here
                            vk.messages.send(
                                chat_id=chat_id,
                                message=f"🎉 @id{user_id}, поздравляем с повышением уровня!",
                                random_id=get_random_id()
                            )
                    
                    if text.startswith('/'):
                        command = text.split()[0][1:]
                        args = text.split()[1:] if len(text.split()) > 1 else []
                        
                        # User commands
                        if command == 'help':
                            response = cmd_help(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'info':
                            response = cmd_info(vk, event)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'stats':
                            response = cmd_stats(vk, event)
                            if response:  # Отправляем сообщение только если есть текстовый ответ
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'getid':
                            response = cmd_getid(vk, event)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        
                        # Fun commands
                        elif command == 'profile':
                            response = cmd_profile(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'daily':
                            response = cmd_daily(vk, event)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'marry':
                            response = cmd_marry(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'divorce':
                            response = cmd_divorce(vk, event)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'rep':
                            response = cmd_rep(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'game':
                            response = cmd_game(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'top':
                            response = cmd_top(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        
                        # Game commands
                        elif command == 'slots':
                            response = cmd_slots(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'duel':
                            response = cmd_duel(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'wheel':
                            response = cmd_wheel(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'flip':
                            response = cmd_flip(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'dice':
                            response = cmd_dice(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'roulette':
                            response = cmd_russian_roulette(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'blackjack':
                            response = cmd_blackjack(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'lottery':
                            response = cmd_lottery(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'numbers':
                            response = cmd_numbers(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'jackpot':
                            response = cmd_jackpot(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'poker':
                            response = cmd_poker(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'tournament':
                            response = cmd_tournament(vk, event)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'baccarat':
                            response = cmd_baccarat(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'crash':
                            response = cmd_crash(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'mines':
                            response = cmd_mines(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        
                        # Utility commands
                        elif command == 'weather':
                            if not args:
                                response = "⚠️ Укажите город"
                            else:
                                city = ' '.join(args)
                                weather = get_weather(city)
                                if weather:
                                    response = (f"🌤 Погода в {city}:\n"
                                              f"🌡 Температура: {weather['temp']}°C\n"
                                              f"🌡 Ощущается как: {weather['feels_like']}°C\n"
                                              f"💨 Ветер: {weather['wind_speed']} м/с\n"
                                              f"💧 Влажность: {weather['humidity']}%\n"
                                              f"📝 {weather['description'].capitalize()}")
                                else:
                                    response = "❌ Не удалось получить погоду"
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        
                        elif command == 'rates':
                            rates = get_currency_rates()
                            if rates:
                                response = (f"💰 Курсы валют:\n"
                                          f"💵 USD: {rates['USD']} ₽\n"
                                          f"💶 EUR: {rates['EUR']} ₽")
                            else:
                                response = "❌ Не удалось получить курсы валют"
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        
                        # Moderator commands
                        elif command == 'kick':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_kick(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'mute':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_mute(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'unmute':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_unmute(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'warn':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_warn(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'unwarn':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_unwarn(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'getban':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_getban(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'getwarn':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_getwarn(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'warnhistory':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_warnhistory(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'staff':
                            if is_moderator(event.obj.message['from_id']):
                                response = cmd_staff(vk, event)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        
                        # Senior moderator commands
                        elif command == 'ban':
                            if is_senior_moderator(event.obj.message['from_id']):
                                response = cmd_ban(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'unban':
                            if is_senior_moderator(event.obj.message['from_id']):
                                response = cmd_unban(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'addmoder':
                            if is_senior_moderator(event.obj.message['from_id']):
                                response = cmd_addmoder(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'removerole':
                            if is_senior_moderator(event.obj.message['from_id']):
                                response = cmd_removerole(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'zov':
                            if is_senior_moderator(event.obj.message['from_id']):
                                response = cmd_zov(vk, event)
                                if response:  # Send if there's a message
                                    vk.messages.send(
                                        chat_id=chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                        elif command == 'online':
                            if is_senior_moderator(event.obj.message['from_id']):
                                response = cmd_online(vk, event)
                                if response:  # Send if there's a message
                                    vk.messages.send(
                                        chat_id=chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                        elif command == 'banlist':
                            if is_senior_moderator(event.obj.message['from_id']):
                                response = cmd_banlist(vk, event)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'onlinelist':
                            if is_senior_moderator(event.obj.message['from_id']):
                                response = cmd_onlinelist(vk, event)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        
                        # Admin commands
                        elif command == 'skick':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_skick(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'quiet':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_quiet(vk, event, args)
                                if response:  # Send if there's a message
                                    vk.messages.send(
                                        chat_id=chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                        elif command == 'sban':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_sban(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'sunban':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_sunban(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'addsenmoder':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_addsenmoder(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'bug':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_bug(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'stats_chat':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_stats_chat(vk, event)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'settings':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_settings(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'addadmin':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_addadmin(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'removeadmin':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_removeadmin(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'massban':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_massban(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'unbanall':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_unbanall(vk, event)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'clearwarns':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_clear_warns(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'resetstats':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_reset_stats(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'adminlist':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_admin_list(vk, event)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'give':
                            response = cmd_give(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'nickname':
                            response = cmd_nickname(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'snick':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_snick(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'nlist':
                            response = cmd_nlist(vk, event)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'achievements':
                            response = cmd_achievements(vk, event)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'music':
                            response = cmd_music(vk, event, args)
                            vk.messages.send(
                                chat_id=chat_id,
                                message=response,
                                random_id=get_random_id()
                            )
                        elif command == 'resetmessages':
                            if is_admin(event.obj.message['from_id']):
                                try:
                                    conn = sqlite3.connect('bot.db')
                                    c = conn.cursor()
                                    c.execute('UPDATE users SET messages_count = 0')
                                    c.execute('DELETE FROM message_history')
                                    conn.commit()
                                    conn.close()
                                    response = "✅ Счетчики сообщений сброшены"
                                except Exception as e:
                                    response = f"❌ Ошибка: {str(e)}"
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'givemoney':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_givemoney(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'filter':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_filter(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'pin':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_pin(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'export':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_export(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'welcome':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_welcome(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'backup':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_backup(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        elif command == 'automod':
                            if is_admin(event.obj.message['from_id']):
                                response = cmd_automod(vk, event, args)
                                vk.messages.send(
                                    chat_id=chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                        
                except Exception as e:
                    error_msg = f"Ошибка при обработке сообщения: {str(e)}"
                    log_error(error_msg, exc_info=True)
                    vk.messages.send(
                        chat_id=chat_id,
                        message="❌ Произошла ошибка при обработке команды",
                        random_id=get_random_id()
                    )
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 