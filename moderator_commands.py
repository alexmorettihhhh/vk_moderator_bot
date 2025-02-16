import sqlite3
from datetime import datetime, timedelta
from vk_api.utils import get_random_id
from utils import extract_user_id

def cmd_mute(vk, event, args):
    if not args or len(args) < 2:
        return "⚠️ Использование: /mute [@пользователь] [время в минутах] [причина]"
    
    try:
        target = args[0]
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
            
        minutes = int(args[1])
        reason = ' '.join(args[2:]) if len(args) > 2 else "Не указана"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        mute_end = datetime.now() + timedelta(minutes=minutes)
        
        c.execute('''UPDATE users 
                    SET is_muted = 1, mute_end = ? 
                    WHERE user_id = ?''', (mute_end, user_id))
        conn.commit()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        response = f"✅ Пользователь @id{user_id} ({user_info['first_name']}) замучен на {minutes} минут\nПричина: {reason}"
        
        conn.close()
        return response
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_unmute(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''UPDATE users 
                    SET is_muted = 0, mute_end = NULL 
                    WHERE user_id = ?''', (user_id,))
        conn.commit()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        response = f"✅ Пользователь @id{user_id} ({user_info['first_name']}) размучен"
        
        conn.close()
        return response
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_warn(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя и причину"
    
    try:
        target = args[0]
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
            
        reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"
        warned_by = event.obj.message['from_id']
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Add warning to history
        c.execute('''INSERT INTO warn_history (user_id, warned_by, reason, timestamp)
                    VALUES (?, ?, ?, ?)''', (user_id, warned_by, reason, datetime.now()))
        
        # Increment warnings count
        c.execute('''UPDATE users 
                    SET warnings = warnings + 1 
                    WHERE user_id = ?''', (user_id,))
        
        # Get current warnings count
        c.execute('SELECT warnings FROM users WHERE user_id = ?', (user_id,))
        warnings = c.fetchone()[0]
        
        conn.commit()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        response = f"⚠️ Пользователь @id{user_id} ({user_info['first_name']}) получил предупреждение ({warnings}/3)\nПричина: {reason}"
        
        conn.close()
        return response
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_unwarn(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''UPDATE users 
                    SET warnings = CASE 
                        WHEN warnings > 0 THEN warnings - 1 
                        ELSE 0 
                    END 
                    WHERE user_id = ?''', (user_id,))
        conn.commit()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        response = f"✅ С пользователя @id{user_id} ({user_info['first_name']}) снято предупреждение"
        
        conn.close()
        return response
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_getban(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('SELECT chat_id, ban_time FROM bans WHERE user_id = ?', (user_id,))
        bans = c.fetchall()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        
        if not bans:
            response = f"✅ Пользователь @id{user_id} ({user_info['first_name']}) не имеет активных банов"
        else:
            response = f"📋 Баны пользователя @id{user_id} ({user_info['first_name']}):\n"
            for chat_id, ban_time in bans:
                response += f"• Чат {chat_id}: с {ban_time}\n"
        
        conn.close()
        return response
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_getwarn(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('SELECT warnings FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        
        if not result:
            response = f"✅ Пользователь @id{user_id} ({user_info['first_name']}) не имеет предупреждений"
        else:
            response = f"📋 Активные предупреждения пользователя @id{user_id} ({user_info['first_name']}): {result[0]}/3"
        
        conn.close()
        return response
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_warnhistory(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''SELECT warned_by, reason, timestamp 
                    FROM warn_history 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC''', (user_id,))
        history = c.fetchall()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        
        if not history:
            response = f"✅ У пользователя @id{user_id} ({user_info['first_name']}) нет истории предупреждений"
        else:
            response = f"📋 История предупреждений пользователя @id{user_id} ({user_info['first_name']}):\n"
            for warned_by, reason, timestamp in history:
                warner_info = vk.users.get(user_ids=[warned_by])[0]
                response += f"• {timestamp} от @id{warned_by} ({warner_info['first_name']}): {reason}\n"
        
        conn.close()
        return response
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_staff(vk, event):
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем всех пользователей с ролями, кроме обычных пользователей
        c.execute('''SELECT user_id, role 
                    FROM users 
                    WHERE role != 'user' 
                    ORDER BY CASE 
                        WHEN role = 'admin' THEN 1 
                        WHEN role = 'senior_moderator' THEN 2 
                        WHEN role = 'moderator' THEN 3 
                    END''')
        staff = c.fetchall()
        conn.close()
        
        if not staff:
            return "📋 Нет пользователей с ролями"
        
        # Собираем все user_id для запроса к VK API
        user_ids = [user_id for user_id, _ in staff]
        
        # Получаем информацию о пользователях через VK API
        users_info = vk.users.get(user_ids=user_ids)
        
        # Создаем словарь для быстрого доступа к информации о пользователях
        users_dict = {user['id']: user for user in users_info}
        
        # Формируем сообщение
        message = "📋 Пользователи с ролями:\n"
        for user_id, role in staff:
            user = users_dict.get(user_id, {'first_name': 'Unknown', 'last_name': 'User'})
            message += f"• @id{user_id} ({user['first_name']} {user['last_name']}) — {role}\n"
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"