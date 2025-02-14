import os
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sqlite3
import json
from fun_commands import (
    cmd_profile, cmd_daily, cmd_marry, cmd_divorce,
    cmd_rep, cmd_game, cmd_top
)
from games import cmd_slots, cmd_duel, cmd_wheel, cmd_flip
from utils import get_weather, get_currency_rates, extract_user_id
from admin_commands import (
    cmd_skick, cmd_quiet, cmd_sban, cmd_sunban,
    cmd_addsenmoder, cmd_bug, cmd_stats_chat, cmd_settings
)
from moderator_commands import (
    cmd_mute, cmd_unmute, cmd_warn, cmd_unwarn,
    cmd_getban, cmd_getwarn, cmd_warnhistory, cmd_staff
)
from senior_moderator_commands import (
    cmd_ban, cmd_unban, cmd_addmoder, cmd_removerole,
    cmd_zov, cmd_online, cmd_banlist, cmd_onlinelist
)
import time
import sys
from requests.exceptions import ConnectionError, ReadTimeout

# Load environment variables
load_dotenv()

# VK Bot configuration
TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))

# Initialize VK session
def init_vk():
    """Инициализация VK сессии"""
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    return vk_session, vk, longpoll

# Database initialization
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    # Create users table with new fields
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  role TEXT DEFAULT 'user',
                  nickname TEXT,
                  warnings INTEGER DEFAULT 0,
                  is_muted INTEGER DEFAULT 0,
                  mute_end TIMESTAMP,
                  messages_count INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1,
                  xp INTEGER DEFAULT 0,
                  balance INTEGER DEFAULT 0,
                  reputation INTEGER DEFAULT 0,
                  last_daily TIMESTAMP)''')
    
    # Create bans table
    c.execute('''CREATE TABLE IF NOT EXISTS bans
                 (user_id INTEGER,
                  chat_id INTEGER,
                  ban_time TIMESTAMP,
                  PRIMARY KEY (user_id, chat_id))''')
    
    # Create warn history table
    c.execute('''CREATE TABLE IF NOT EXISTS warn_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  warned_by INTEGER,
                  reason TEXT,
                  timestamp TIMESTAMP)''')
    
    # Create marriages table
    c.execute('''CREATE TABLE IF NOT EXISTS marriages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user1_id INTEGER,
                  user2_id INTEGER,
                  marriage_date TIMESTAMP,
                  UNIQUE(user1_id, user2_id))''')
    
    # Create achievements table
    c.execute('''CREATE TABLE IF NOT EXISTS achievements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  achievement_type TEXT,
                  achievement_date TIMESTAMP)''')
    
    # Create chat_settings table with quiet_end column
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings
                 (chat_id INTEGER PRIMARY KEY,
                  quiet_mode INTEGER DEFAULT 0,
                  quiet_end TIMESTAMP,
                  welcome_message TEXT,
                  auto_warn INTEGER DEFAULT 0,
                  max_warnings INTEGER DEFAULT 3)''')
    
    # Create reputation_history table
    c.execute('''CREATE TABLE IF NOT EXISTS reputation_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_user_id INTEGER,
                  to_user_id INTEGER,
                  amount INTEGER,
                  reason TEXT,
                  timestamp TIMESTAMP)''')
    
    # Create bug_reports table
    c.execute('''CREATE TABLE IF NOT EXISTS bug_reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  reporter_id INTEGER,
                  description TEXT,
                  report_time TIMESTAMP,
                  status TEXT DEFAULT 'new')''')
    
    # Create bot_chats table
    c.execute('''CREATE TABLE IF NOT EXISTS bot_chats
                 (chat_id INTEGER PRIMARY KEY,
                  join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_active INTEGER DEFAULT 1)''')
    
    # Add quiet_end column if it doesn't exist
    try:
        c.execute('ALTER TABLE chat_settings ADD COLUMN quiet_end TIMESTAMP')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

# User commands
def cmd_info(vk, event):
    message = "📚 Официальные ресурсы проекта:\n• Группа ВК: vk.com/group\n• Сайт: example.com"
    vk.messages.send(
        chat_id=event.chat_id,
        message=message,
        random_id=get_random_id()
    )

def cmd_stats(vk, event):
    user_id = event.obj.message['from_id']
    user_info = vk.users.get(user_ids=user_id)[0]
    message = f"📊 Информация о пользователе:\nID: {user_id}\nИмя: {user_info['first_name']} {user_info['last_name']}"
    vk.messages.send(
        chat_id=event.chat_id,
        message=message,
        random_id=get_random_id()
    )

def cmd_getid(vk, event):
    user_id = event.obj.message['from_id']
    message = f"🆔 Ваш ID: {user_id}"
    vk.messages.send(
        chat_id=event.chat_id,
        message=message,
        random_id=get_random_id()
    )

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
        message += "• /top [level/messages/balance/rep] — топ игроков\n\n"
        
        message += "🎮 Игровые команды:\n"
        message += "• /slots [ставка] — игровые автоматы\n"
        message += "• /duel [ID] [ставка] — дуэль\n"
        message += "• /wheel [ставка] [red/black/green] — рулетка\n"
        message += "• /flip [ставка] [heads/tails] — монетка\n\n"
        
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
            message += "• /bug [описание] — сообщить о баге\n"
        
        return message
    except Exception as e:
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
                    SET xp = ?, level = ?, messages_count = messages_count + 1 
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
        
        c.execute('''INSERT INTO users (user_id, xp, level, messages_count, role) 
                    VALUES (?, ?, 1, 1, ?)''', (user_id, xp_amount, role))
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

# Main event loop
def main():
    init_db()
    print("Bot started")
    
    while True:
        try:
            # Инициализация VK
            vk_session, vk, longpoll = init_vk()
            
            # Основной цикл
            for event in longpoll.listen():
                if event.type == VkBotEventType.MESSAGE_NEW and event.from_chat:
                    try:
                        message = event.obj.message['text'].lower()
                        user_id = event.obj.message['from_id']
                        
                        # Проверяем режим тишины и права пользователя
                        if is_quiet_mode(event.chat_id):
                            user_role = get_user_role(user_id)
                            if user_role not in ['admin', 'senior_moderator', 'moderator']:
                                # Удаляем сообщение от обычного пользователя
                                try:
                                    vk.messages.delete(
                                        peer_id=2000000000 + event.chat_id,
                                        conversation_message_ids=[event.obj.message['conversation_message_id']],
                                        delete_for_all=1
                                    )
                                    continue
                                except:
                                    pass
                        
                        # Add XP for message (if not a command)
                        if not message.startswith('/'):
                            if add_xp(vk, event, user_id, 10):  # Pass event object here
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=f"🎉 @id{user_id}, поздравляем с повышением уровня!",
                                    random_id=get_random_id()
                                )
                        
                        if message.startswith('/'):
                            command = message.split()[0][1:]
                            args = message.split()[1:] if len(message.split()) > 1 else []
                            
                            # User commands
                            if command == 'help':
                                response = cmd_help(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'info':
                                cmd_info(vk, event)
                            elif command == 'stats':
                                cmd_stats(vk, event)
                            elif command == 'getid':
                                cmd_getid(vk, event)
                            
                            # Fun commands
                            elif command == 'profile':
                                response = cmd_profile(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'daily':
                                response = cmd_daily(vk, event)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'marry':
                                response = cmd_marry(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'divorce':
                                response = cmd_divorce(vk, event)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'rep':
                                response = cmd_rep(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'game':
                                response = cmd_game(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'top':
                                response = cmd_top(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            
                            # Game commands
                            elif command == 'slots':
                                response = cmd_slots(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'duel':
                                response = cmd_duel(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'wheel':
                                response = cmd_wheel(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            elif command == 'flip':
                                response = cmd_flip(vk, event, args)
                                vk.messages.send(
                                    chat_id=event.chat_id,
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
                                    chat_id=event.chat_id,
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
                                    chat_id=event.chat_id,
                                    message=response,
                                    random_id=get_random_id()
                                )
                            
                            # Moderator commands
                            elif command == 'kick':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_kick(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'mute':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_mute(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'unmute':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_unmute(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'warn':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_warn(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'unwarn':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_unwarn(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'getban':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_getban(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'getwarn':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_getwarn(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'warnhistory':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_warnhistory(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'staff':
                                if is_moderator(event.obj.message['from_id']):
                                    response = cmd_staff(vk, event)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            
                            # Senior moderator commands
                            elif command == 'ban':
                                if is_senior_moderator(event.obj.message['from_id']):
                                    response = cmd_ban(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'unban':
                                if is_senior_moderator(event.obj.message['from_id']):
                                    response = cmd_unban(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'addmoder':
                                if is_senior_moderator(event.obj.message['from_id']):
                                    response = cmd_addmoder(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'removerole':
                                if is_senior_moderator(event.obj.message['from_id']):
                                    response = cmd_removerole(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'zov':
                                if is_senior_moderator(event.obj.message['from_id']):
                                    response = cmd_zov(vk, event)
                                    if response:  # Only send if there's an error message
                                        vk.messages.send(
                                            chat_id=event.chat_id,
                                            message=response,
                                            random_id=get_random_id()
                                        )
                            elif command == 'online':
                                if is_senior_moderator(event.obj.message['from_id']):
                                    response = cmd_online(vk, event)
                                    if response:  # Only send if there's an error message
                                        vk.messages.send(
                                            chat_id=event.chat_id,
                                            message=response,
                                            random_id=get_random_id()
                                        )
                            elif command == 'banlist':
                                if is_senior_moderator(event.obj.message['from_id']):
                                    response = cmd_banlist(vk, event)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'onlinelist':
                                if is_senior_moderator(event.obj.message['from_id']):
                                    response = cmd_onlinelist(vk, event)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            
                            # Admin commands
                            elif command == 'skick':
                                if is_admin(event.obj.message['from_id']):
                                    response = cmd_skick(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'quiet':
                                if is_admin(event.obj.message['from_id']):
                                    response = cmd_quiet(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'sban':
                                if is_admin(event.obj.message['from_id']):
                                    response = cmd_sban(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'sunban':
                                if is_admin(event.obj.message['from_id']):
                                    response = cmd_sunban(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'addsenmoder':
                                if is_admin(event.obj.message['from_id']):
                                    response = cmd_addsenmoder(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'bug':
                                if is_admin(event.obj.message['from_id']):
                                    response = cmd_bug(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'stats_chat':
                                if is_admin(event.obj.message['from_id']):
                                    response = cmd_stats_chat(vk, event)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            elif command == 'settings':
                                if is_admin(event.obj.message['from_id']):
                                    response = cmd_settings(vk, event, args)
                                    vk.messages.send(
                                        chat_id=event.chat_id,
                                        message=response,
                                        random_id=get_random_id()
                                    )
                            
                    except Exception as e:
                        print(f"Error processing message: {str(e)}")
                        continue
        
        except (ConnectionError, ReadTimeout) as e:
            print(f"Connection error: {str(e)}")
            print("Reconnecting in 5 seconds...")
            time.sleep(5)
            continue
        
        except Exception as e:
            print(f"Critical error: {str(e)}")
            print("Restarting in 30 seconds...")
            time.sleep(30)
            continue

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0) 