import sqlite3
from datetime import datetime, timedelta
from vk_api.utils import get_random_id
from utils import get_chat_stats, parse_duration, format_duration, extract_user_id

def cmd_skick(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя и причину"
    
    try:
        target = args[0]
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
            
        reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('SELECT chat_id FROM bot_chats')
        chats = c.fetchall()
        conn.close()
        
        kick_count = 0
        for chat_id in chats:
            try:
                vk.messages.removeChatUser(
                    chat_id=chat_id[0],
                    user_id=user_id
                )
                kick_count += 1
            except:
                continue
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"👢 Пользователь @id{user_id} ({user_info['first_name']}) исключен из {kick_count} бесед\nПричина: {reason}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_quiet(vk, event, args):
    """Управление режимом тишины в беседе"""
    conn = None
    try:
        duration = None
        if args:
            try:
                duration = parse_duration(args[0])
                if duration == 0:
                    return "⚠️ Время должно быть больше 0"
            except:
                return "⚠️ Неверный формат времени. Используйте: 30m, 1h, 2h30m и т.д."
        
        conn = sqlite3.connect('bot.db', timeout=20)
        c = conn.cursor()
        
        c.execute('SELECT quiet_mode, quiet_end FROM chat_settings WHERE chat_id = ?', (event.chat_id,))
        result = c.fetchone()
        
        if result is None:
            c.execute('INSERT INTO chat_settings (chat_id, quiet_mode, quiet_end) VALUES (?, 1, ?)', 
                     (event.chat_id, datetime.now() + timedelta(seconds=duration) if duration else None))
            new_mode = True
        else:
            current_mode, current_end = result
            new_mode = not current_mode
            if new_mode and duration:
                end_time = datetime.now() + timedelta(seconds=duration)
                c.execute('UPDATE chat_settings SET quiet_mode = ?, quiet_end = ? WHERE chat_id = ?', 
                         (1, end_time, event.chat_id))
            else:
                c.execute('UPDATE chat_settings SET quiet_mode = ?, quiet_end = NULL WHERE chat_id = ?', 
                         (int(new_mode), event.chat_id))
        
        conn.commit()
        
        if duration and new_mode:
            duration_str = format_duration(duration)
            message = f"🤫 Режим тишины включен на {duration_str}\nВ этот период сообщения от обычных пользователей будут удаляться."
        else:
            message = f"{'🤫 Режим тишины включен. Сообщения от обычных пользователей будут удаляться.' if new_mode else '🔊 Режим тишины выключен.'}"
        
        return message
        
    except sqlite3.Error as e:
        return f"❌ Ошибка базы данных: {str(e)}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def cmd_sban(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя и причину"
    
    try:
        target = args[0]
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
            
        reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('SELECT chat_id FROM bot_chats')
        chats = c.fetchall()
        
        ban_time = datetime.now()
        for chat_id in chats:
            c.execute('''INSERT OR REPLACE INTO bans (user_id, chat_id, ban_time)
                        VALUES (?, ?, ?)''', (user_id, chat_id[0], ban_time))
            try:
                vk.messages.removeChatUser(
                    chat_id=chat_id[0],
                    user_id=user_id
                )
            except:
                continue
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"🚫 Пользователь @id{user_id} ({user_info['first_name']}) заблокирован во всех беседах\nПричина: {reason}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_sunban(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ Пользователь @id{user_id} ({user_info['first_name']}) разблокирован во всех беседах"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_addsenmoder(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO users (user_id, role)
                    VALUES (?, 'senior_moderator')''', (user_id,))
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ Пользователю @id{user_id} ({user_info['first_name']}) выдана роль старшего модератора"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_bug(vk, event, args):
    if not args:
        return "⚠️ Укажите описание бага"
    
    try:
        bug_description = ' '.join(args)
        reporter_id = event.obj.message['from_id']
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''INSERT INTO bug_reports (reporter_id, description, report_time)
                    VALUES (?, ?, ?)''', (reporter_id, bug_description, datetime.now()))
        
        conn.commit()
        conn.close()
        
        dev_chat_id = 1  # Replace with actual developer chat ID
        vk.messages.send(
            chat_id=dev_chat_id,
            message=f"🐛 Новый баг репорт от @id{reporter_id}:\n{bug_description}",
            random_id=get_random_id()
        )
        
        return "✅ Баг репорт отправлен разработчикам"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_stats_chat(vk, event):
    """Статистика беседы"""
    try:
        stats = get_chat_stats(vk, event.chat_id)
        if not stats:
            return "❌ Не удалось получить статистику беседы"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем настройки беседы
        c.execute('SELECT quiet_mode, welcome_message FROM chat_settings WHERE chat_id = ?', 
                 (event.chat_id,))
        settings = c.fetchone() or (0, None)
        
        # Получаем количество варнов в беседе
        c.execute('''SELECT COUNT(*) FROM warn_history 
                    WHERE user_id IN (
                        SELECT user_id FROM users 
                        WHERE warnings > 0
                    )''')
        warns_count = c.fetchone()[0]
        
        # Получаем количество банов в беседе
        c.execute('SELECT COUNT(*) FROM bans WHERE chat_id = ?', (event.chat_id,))
        bans_count = c.fetchone()[0]
        
        conn.close()
        
        message = "📊 Статистика беседы:\n\n"
        message += f"👥 Всего участников: {stats['total_members']}\n"
        message += f"🟢 Онлайн: {stats['online_count']}\n"
        message += f"👮 Администраторов: {stats['admins_count']}\n"
        message += f"⚠️ Активных предупреждений: {warns_count}\n"
        message += f"🚫 Активных банов: {bans_count}\n"
        message += f"🤫 Режим тишины: {'Включен' if settings[0] else 'Выключен'}\n"
        if settings[1]:
            message += f"👋 Приветствие: Установлено\n"
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_settings(vk, event, args):
    """Управление настройками беседы"""
    if not args:
        return "⚠️ Укажите параметр и значение"
    
    try:
        param = args[0].lower()
        value = ' '.join(args[1:]) if len(args) > 1 else None
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        if param == 'welcome':
            if not value:
                return "⚠️ Укажите текст приветствия"
            c.execute('''INSERT OR REPLACE INTO chat_settings (chat_id, welcome_message)
                        VALUES (?, ?)''', (event.chat_id, value))
            message = "✅ Приветствие установлено"
        
        elif param == 'autowarn':
            enabled = value == 'on'
            c.execute('''INSERT OR REPLACE INTO chat_settings (chat_id, auto_warn)
                        VALUES (?, ?)''', (event.chat_id, int(enabled)))
            message = f"✅ Автоварн {'включен' if enabled else 'выключен'}"
        
        elif param == 'maxwarns':
            try:
                max_warns = int(value)
                if max_warns < 1 or max_warns > 10:
                    return "⚠️ Количество предупреждений должно быть от 1 до 10"
                c.execute('''INSERT OR REPLACE INTO chat_settings (chat_id, max_warnings)
                            VALUES (?, ?)''', (event.chat_id, max_warns))
                message = f"✅ Максимальное количество предупреждений установлено: {max_warns}"
            except:
                return "⚠️ Укажите корректное число предупреждений"
        
        else:
            return "⚠️ Неизвестный параметр. Доступные параметры: welcome, autowarn, maxwarns"
        
        conn.commit()
        conn.close()
        
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}" 