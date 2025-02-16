import sqlite3
from datetime import datetime, timedelta
from vk_api.utils import get_random_id
from utils import get_chat_stats, parse_duration, format_duration, extract_user_id
from logger import log_moderation, log_error

def is_admin(user_id):
    """Проверка является ли пользователь администратором"""
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 'admin'

def get_user_role(user_id):
    """Получить роль пользователя"""
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 'user'

def cmd_skick(vk, event, args):
    """Исключить пользователя из всех бесед"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите пользователя и причину"
    
    try:
        target = args[0]
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
            
        reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"
        
        # Проверяем, не пытаются ли кикнуть администратора
        if is_admin(user_id):
            return "⚠️ Невозможно исключить администратора"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('SELECT chat_id FROM bot_chats WHERE is_active = 1')
        chats = c.fetchall()
        conn.close()
        
        kick_count = 0
        failed_chats = []
        for chat_id in chats:
            try:
                vk.messages.removeChatUser(
                    chat_id=chat_id[0],
                    user_id=user_id
                )
                kick_count += 1
            except Exception as e:
                failed_chats.append(str(chat_id[0]))
                continue
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        log_moderation(event.obj.message['from_id'], 'SKICK', user_id, reason)
        
        response = f"👢 Пользователь @id{user_id} ({user_info['first_name']}) исключен из {kick_count} бесед\nПричина: {reason}"
        if failed_chats:
            response += f"\n⚠️ Не удалось исключить из бесед: {', '.join(failed_chats)}"
        return response
    except Exception as e:
        log_error(f"Ошибка в команде skick: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_quiet(vk, event, args):
    """Управление режимом тишины в беседе"""
    try:
        if not args:
            new_mode = True
            duration = None
        else:
            new_mode = args[0].lower() not in ['off', '0', 'false']
            duration = int(args[1]) if len(args) > 1 else None
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        if duration:
            quiet_end = datetime.now() + timedelta(minutes=duration)
        else:
            quiet_end = None
        
        c.execute('''UPDATE chat_settings 
                    SET quiet_mode = ?, quiet_end = ? 
                    WHERE chat_id = ?''', 
                    (1 if new_mode else 0, quiet_end, event.chat_id))
        
        if c.rowcount == 0:
            c.execute('''INSERT INTO chat_settings 
                        (chat_id, quiet_mode, quiet_end) 
                        VALUES (?, ?, ?)''', 
                        (event.chat_id, 1 if new_mode else 0, quiet_end))
        
        conn.commit()
        conn.close()
        
        if duration and new_mode:
            duration_str = format_duration(duration)
            return f"🤫 Режим тишины включен на {duration_str}\nВ этот период сообщения от обычных пользователей будут удаляться."
        else:
            return f"{'🤫 Режим тишины включен. Сообщения от обычных пользователей будут удаляться.' if new_mode else '🔊 Режим тишины выключен.'}"
        
    except sqlite3.Error as e:
        log_error(f"Ошибка базы данных в команде quiet: {str(e)}", exc_info=True)
        return f"❌ Ошибка базы данных: {str(e)}"
    except Exception as e:
        log_error(f"Ошибка в команде quiet: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def cmd_sban(vk, event, args):
    """Заблокировать пользователя во всех беседах"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите пользователя и причину"
    
    try:
        target = args[0]
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        # Проверяем, не пытаются ли забанить администратора
        if is_admin(user_id):
            return "⚠️ Невозможно заблокировать администратора"
            
        reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем список всех активных бесед
        c.execute('SELECT chat_id FROM bot_chats WHERE is_active = 1')
        chats = c.fetchall()
        
        ban_time = datetime.now()
        banned_chats = []
        failed_chats = []
        
        for chat_id in chats:
            chat_id = chat_id[0]
            
            try:
                # Проверяем, есть ли пользователь в беседе
                members = vk.messages.getConversationMembers(peer_id=2000000000 + chat_id)
                member_ids = [member['member_id'] for member in members['items']]
                
                if user_id in member_ids:
                    # Исключаем пользователя из беседы
                    vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
                    banned_chats.append(chat_id)
                    
                    # Добавляем запись о бане в базу данных
                    c.execute('''INSERT OR REPLACE INTO bans (user_id, chat_id, ban_time)
                                VALUES (?, ?, ?)''', (user_id, chat_id, ban_time))
                    
                    # Логируем действие для каждой беседы
                    log_moderation(event.obj.message['from_id'], 'BAN', user_id, f"Беседа {chat_id}: {reason}")
            except Exception as e:
                failed_chats.append(str(chat_id))
                log_error(f"Ошибка при обработке чата {chat_id}: {str(e)}")
                continue
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        response = (f"🚫 Пользователь @id{user_id} ({user_info['first_name']} {user_info['last_name']}) "
                   f"заблокирован в {len(banned_chats)} беседах\n"
                   f"Причина: {reason}")
        
        if failed_chats:
            response += f"\n⚠️ Не удалось заблокировать в беседах: {', '.join(failed_chats)}"
        
        return response
    
    except Exception as e:
        log_error(f"Ошибка в команде sban: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_sunban(vk, event, args):
    """Разблокировать пользователя во всех беседах"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем список бесед, где пользователь забанен
        c.execute('SELECT chat_id FROM bans WHERE user_id = ?', (user_id,))
        banned_chats = c.fetchall()
        
        if not banned_chats:
            conn.close()
            user_info = vk.users.get(user_ids=[user_id])[0]
            return f"⚠️ Пользователь @id{user_id} ({user_info['first_name']}) не имеет активных банов"
        
        # Удаляем все записи о банах пользователя
        c.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        
        log_moderation(event.obj.message['from_id'], 'UNBAN', user_id, f"Разбан во всех беседах ({len(banned_chats)} бесед)")
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ Пользователь @id{user_id} ({user_info['first_name']}) разблокирован во всех беседах ({len(banned_chats)} бесед)"
    except Exception as e:
        log_error(f"Ошибка в команде sunban: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_addsenmoder(vk, event, args):
    """Назначить пользователя старшим модератором"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        # Проверяем, не является ли пользователь уже администратором
        if is_admin(user_id):
            return "⚠️ Пользователь уже является администратором"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем текущую роль пользователя
        c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
        current_role = c.fetchone()
        
        if current_role and current_role[0] == 'senior_moderator':
            return "⚠️ Пользователь уже является старшим модератором"
        
        # Назначаем пользователя старшим модератором
        c.execute('''INSERT OR REPLACE INTO users 
                    (user_id, role, messages_count, level, xp, balance, reputation)
                    VALUES (?, 'senior_moderator', 
                    COALESCE((SELECT messages_count FROM users WHERE user_id = ?), 0),
                    COALESCE((SELECT level FROM users WHERE user_id = ?), 1),
                    COALESCE((SELECT xp FROM users WHERE user_id = ?), 0),
                    COALESCE((SELECT balance FROM users WHERE user_id = ?), 0),
                    COALESCE((SELECT reputation FROM users WHERE user_id = ?), 0))''',
                    (user_id, user_id, user_id, user_id, user_id, user_id))
        
        conn.commit()
        conn.close()
        
        log_moderation(event.obj.message['from_id'], 'ADD_SENIOR_MODERATOR', user_id)
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        
        # Уведомляем других администраторов
        try:
            admin_message = f"👑 Новый старший модератор:\n@id{user_id} ({user_info['first_name']})"
            notify_admins(vk, admin_message, exclude_id=event.obj.message['from_id'])
        except:
            pass
        
        return f"✅ Пользователь @id{user_id} ({user_info['first_name']}) назначен старшим модератором"
    except Exception as e:
        log_error(f"Ошибка в команде addsenmoder: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_bug(vk, event, args):
    """Отправить сообщение о баге разработчику"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите описание бага"
    
    try:
        bug_description = ' '.join(args)
        reporter_id = event.obj.message['from_id']
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''INSERT INTO bug_reports (reporter_id, description, report_time, status)
                    VALUES (?, ?, ?, 'new')''', (reporter_id, bug_description, datetime.now()))
        
        bug_id = c.lastrowid
        
        conn.commit()
        conn.close()
        
        # Получаем информацию о репортере
        reporter_info = vk.users.get(user_ids=[reporter_id])[0]
        
        # Формируем сообщение о баге
        bug_message = (f"🐛 Новый баг репорт #{bug_id}\n"
                      f"От: @id{reporter_id} ({reporter_info['first_name']} {reporter_info['last_name']})\n"
                      f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                      f"Описание: {bug_description}")
        
        # Уведомляем всех администраторов
        notify_admins(vk, bug_message)
        
        return f"✅ Баг репорт #{bug_id} отправлен администраторам"
    except Exception as e:
        log_error(f"Ошибка в команде bug: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def notify_admins(vk, message, exclude_id=None):
    """Отправить сообщение всем администраторам"""
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем список всех администраторов
        c.execute('SELECT user_id FROM users WHERE role = "admin"')
        admins = c.fetchall()
        conn.close()
        
        for admin_id in admins:
            admin_id = admin_id[0]
            if admin_id != exclude_id:  # Пропускаем указанный ID
                try:
                    vk.messages.send(
                        user_id=admin_id,
                        message=message,
                        random_id=get_random_id()
                    )
                except:
                    continue
        return None
    except:
        return None  # Игнорируем ошибки при отправке уведомлений

def cmd_stats_chat(vk, event):
    """Статистика беседы"""
    try:
        stats = get_chat_stats(vk, event.chat_id)
        if not stats:
            return "❌ Не удалось получить статистику беседы"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем настройки беседы
        c.execute('SELECT quiet_mode, welcome_message, auto_warn, max_warnings FROM chat_settings WHERE chat_id = ?', 
                 (event.chat_id,))
        settings = c.fetchone() or (0, None, 0, 3)
        
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
        
        # Получаем статистику сообщений за последние 24 часа
        yesterday = datetime.now() - timedelta(days=1)
        c.execute('''SELECT COUNT(*) FROM message_history 
                    WHERE chat_id = ? AND timestamp > ?''', 
                    (event.chat_id, yesterday))
        messages_24h = c.fetchone()[0]
        
        conn.close()
        
        message = "📊 Статистика беседы:\n\n"
        message += f"👥 Всего участников: {stats['total_members']}\n"
        message += f"🟢 Онлайн: {stats['online_count']}\n"
        message += f"👮 Администраторов: {stats['admins_count']}\n"
        message += f"⚠️ Активных предупреждений: {warns_count}\n"
        message += f"🚫 Активных банов: {bans_count}\n"
        message += f"💬 Сообщений за 24 часа: {messages_24h}\n\n"
        message += "⚙️ Настройки беседы:\n"
        message += f"🤫 Режим тишины: {'Включен' if settings[0] else 'Выключен'}\n"
        message += f"👋 Приветствие: {'Установлено' if settings[1] else 'Не установлено'}\n"
        message += f"⚠️ Автоварн: {'Включен' if settings[2] else 'Выключен'}\n"
        message += f"❗ Максимум предупреждений: {settings[3]}"
        
        return message
    except Exception as e:
        log_error(f"Ошибка в команде stats_chat: {str(e)}", exc_info=True)
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
        
        elif param == 'antispam':
            if not value:
                return "⚠️ Укажите on/off"
            enabled = value.lower() == 'on'
            c.execute('''INSERT OR REPLACE INTO chat_settings (chat_id, antispam_enabled)
                        VALUES (?, ?)''', (event.chat_id, int(enabled)))
            message = f"✅ Антиспам {'включен' if enabled else 'выключен'}"
        
        else:
            return "⚠️ Неизвестный параметр. Доступные параметры: welcome, autowarn, maxwarns, antispam"
        
        conn.commit()
        conn.close()
        
        log_moderation(event.obj.message['from_id'], 'SETTINGS_CHANGE', event.chat_id, f"{param}: {value}")
        
        return message
    except Exception as e:
        log_error(f"Ошибка в команде settings: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_addadmin(vk, event, args):
    """Назначить пользователя администратором"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        if is_admin(user_id):
            return "⚠️ Пользователь уже является администратором"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO users 
                    (user_id, role, messages_count, level, xp, balance, reputation)
                    VALUES (?, 'admin', 
                    COALESCE((SELECT messages_count FROM users WHERE user_id = ?), 0),
                    COALESCE((SELECT level FROM users WHERE user_id = ?), 1),
                    COALESCE((SELECT xp FROM users WHERE user_id = ?), 0),
                    COALESCE((SELECT balance FROM users WHERE user_id = ?), 0),
                    COALESCE((SELECT reputation FROM users WHERE user_id = ?), 0))''',
                    (user_id, user_id, user_id, user_id, user_id, user_id))
        
        conn.commit()
        conn.close()
        
        log_moderation(event.obj.message['from_id'], 'ADD_ADMIN', user_id)
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        
        # Уведомляем других администраторов
        admin_message = f"👑 Новый администратор:\n@id{user_id} ({user_info['first_name']})"
        notify_admins(vk, admin_message, exclude_id=event.obj.message['from_id'])
        
        return f"✅ Пользователь @id{user_id} ({user_info['first_name']}) назначен администратором"
    except Exception as e:
        log_error(f"Ошибка в команде addadmin: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_removeadmin(vk, event, args):
    """Снять администратора с должности"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        if not is_admin(user_id):
            return "⚠️ Пользователь не является администратором"
        
        # Проверяем количество оставшихся администраторов
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
        admin_count = c.fetchone()[0]
        
        if admin_count <= 1:
            return "⚠️ Невозможно снять последнего администратора"
        
        c.execute('''UPDATE users SET role = 'user' WHERE user_id = ?''', (user_id,))
        conn.commit()
        conn.close()
        
        log_moderation(event.obj.message['from_id'], 'REMOVE_ADMIN', user_id)
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        
        # Уведомляем других администраторов
        admin_message = f"👑 Администратор снят с должности:\n@id{user_id} ({user_info['first_name']})"
        notify_admins(vk, admin_message, exclude_id=event.obj.message['from_id'])
        
        return f"✅ Пользователь @id{user_id} ({user_info['first_name']}) снят с должности администратора"
    except Exception as e:
        log_error(f"Ошибка в команде removeadmin: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_massban(vk, event, args):
    """Массовый бан пользователей"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args or len(args) < 2:
        return "⚠️ Укажите список пользователей и причину"
    
    try:
        targets = args[:-1]  # Все аргументы кроме последнего - это цели
        reason = args[-1]  # Последний аргумент - причина
        
        banned_users = []
        failed_users = []
        
        for target in targets:
            try:
                user_id = extract_user_id(vk, target)
                if not user_id:
                    failed_users.append(target)
                    continue
                
                if is_admin(user_id):
                    failed_users.append(f"@id{user_id}")
                    continue
                
                # Выполняем бан пользователя
                ban_result = cmd_sban(vk, event, [str(user_id), reason])
                if "заблокирован" in ban_result:
                    banned_users.append(f"@id{user_id}")
                else:
                    failed_users.append(f"@id{user_id}")
            except:
                failed_users.append(target)
        
        response = f"🚫 Массовый бан завершен\nПричина: {reason}\n"
        if banned_users:
            response += f"\n✅ Успешно заблокированы:\n{', '.join(banned_users)}"
        if failed_users:
            response += f"\n❌ Не удалось заблокировать:\n{', '.join(failed_users)}"
        
        return response
    except Exception as e:
        log_error(f"Ошибка в команде massban: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_unbanall(vk, event):
    """Разбанить всех пользователей в беседе"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
    
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем список всех забаненных пользователей
        c.execute('SELECT DISTINCT user_id FROM bans WHERE chat_id = ?', (event.chat_id,))
        banned_users = c.fetchall()
        
        if not banned_users:
            return "✅ В беседе нет забаненных пользователей"
        
        # Разбаниваем каждого пользователя
        unbanned_count = 0
        for user_id in banned_users:
            user_id = user_id[0]
            c.execute('DELETE FROM bans WHERE user_id = ? AND chat_id = ?', (user_id, event.chat_id))
            unbanned_count += 1
            
            log_moderation(event.obj.message['from_id'], 'UNBAN', user_id, "Массовый разбан")
        
        conn.commit()
        conn.close()
        
        return f"✅ Разбанено {unbanned_count} пользователей"
    except Exception as e:
        log_error(f"Ошибка в команде unbanall: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_clear_warns(vk, event, args):
    """Очистить все предупреждения у пользователя"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем текущее количество предупреждений
        c.execute('SELECT warnings FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        
        if not result or result[0] == 0:
            return "✅ У пользователя нет предупреждений"
        
        # Очищаем предупреждения
        c.execute('UPDATE users SET warnings = 0 WHERE user_id = ?', (user_id,))
        c.execute('DELETE FROM warn_history WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        
        log_moderation(event.obj.message['from_id'], 'CLEAR_WARNS', user_id)
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ У пользователя @id{user_id} ({user_info['first_name']}) очищены все предупреждения"
    except Exception as e:
        log_error(f"Ошибка в команде clear_warns: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_reset_stats(vk, event, args):
    """Сбросить статистику пользователя"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Сохраняем роль пользователя
        current_role = get_user_role(user_id)
        
        # Сбрасываем статистику
        c.execute('''UPDATE users 
                    SET messages_count = 0,
                        level = 1,
                        xp = 0,
                        balance = 0,
                        reputation = 0
                    WHERE user_id = ?''', (user_id,))
        
        conn.commit()
        conn.close()
        
        log_moderation(event.obj.message['from_id'], 'RESET_STATS', user_id)
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ Статистика пользователя @id{user_id} ({user_info['first_name']}) сброшена"
    except Exception as e:
        log_error(f"Ошибка в команде reset_stats: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_admin_list(vk, event):
    """Показать список всех администраторов"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
    
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''SELECT user_id, 
                           messages_count,
                           level,
                           last_activity
                    FROM users 
                    WHERE role = 'admin'
                    ORDER BY level DESC''')
        admins = c.fetchall()
        
        if not admins:
            return "❌ Администраторы не найдены"
        
        # Получаем информацию о пользователях через VK API
        admin_ids = [admin[0] for admin in admins]
        users_info = vk.users.get(user_ids=admin_ids)
        users_dict = {user['id']: user for user in users_info}
        
        message = "👑 Список администраторов:\n\n"
        
        for admin_id, messages, level, last_activity in admins:
            user = users_dict.get(admin_id, {'first_name': 'Unknown', 'last_name': 'User'})
            last_seen = "Неизвестно" if not last_activity else datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y %H:%M')
            
            message += f"👤 @id{admin_id} ({user['first_name']} {user['last_name']})\n"
            message += f"📊 Уровень: {level}\n"
            message += f"💬 Сообщений: {messages}\n"
            message += f"🕒 Последняя активность: {last_seen}\n\n"
        
        return message
    except Exception as e:
        log_error(f"Ошибка в команде admin_list: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}" 