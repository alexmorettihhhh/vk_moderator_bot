import sqlite3
from datetime import datetime
import json
import os
from logger import log_error, log_moderation
import re
from vk_api.utils import get_random_id

def is_admin(user_id):
    """Проверка является ли пользователь администратором"""
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 'admin'

def cmd_filter(vk, event, args):
    """Управление фильтрами слов"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return "⚠️ Использование:\n/filter add [слово] — добавить слово\n/filter remove [слово] — удалить слово\n/filter list — список слов"
    
    action = args[0].lower()
    
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Создаем таблицу, если её нет
        c.execute('''CREATE TABLE IF NOT EXISTS word_filters
                    (chat_id INTEGER,
                     word TEXT,
                     added_by INTEGER,
                     added_time TIMESTAMP,
                     PRIMARY KEY (chat_id, word))''')
        
        if action == "add" and len(args) > 1:
            word = args[1].lower()
            c.execute('''INSERT OR REPLACE INTO word_filters 
                        (chat_id, word, added_by, added_time)
                        VALUES (?, ?, ?, ?)''',
                        (event.chat_id, word, event.obj.message['from_id'], datetime.now()))
            conn.commit()
            return f"✅ Слово '{word}' добавлено в фильтр"
            
        elif action == "remove" and len(args) > 1:
            word = args[1].lower()
            c.execute('''DELETE FROM word_filters 
                        WHERE chat_id = ? AND word = ?''',
                        (event.chat_id, word))
            conn.commit()
            return f"✅ Слово '{word}' удалено из фильтра"
            
        elif action == "list":
            c.execute('''SELECT word FROM word_filters 
                        WHERE chat_id = ?
                        ORDER BY word''', (event.chat_id,))
            words = c.fetchall()
            
            if not words:
                return "📝 Список запрещенных слов пуст"
                
            message = "📝 Список запрещенных слов:\n\n"
            for word in words:
                message += f"• {word[0]}\n"
            return message
            
        else:
            return "⚠️ Неверная команда"
            
    except Exception as e:
        log_error(f"Ошибка в команде filter: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"
    finally:
        if conn:
            conn.close()

def cmd_pin(vk, event, args):
    """Закрепление сообщения"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    try:
        # Если сообщение является ответом на другое сообщение
        if 'reply_message' in event.obj.message:
            conversation_message_id = event.obj.message['reply_message']['conversation_message_id']
            
            # Закрепляем сообщение
            vk.messages.pin(
                peer_id=2000000000 + event.chat_id,
                conversation_message_id=conversation_message_id
            )
            
            return "📌 Сообщение закреплено"
        else:
            return "⚠️ Ответьте на сообщение, которое хотите закрепить"
            
    except Exception as e:
        log_error(f"Ошибка в команде pin: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"

def cmd_export(vk, event, args):
    """Экспорт данных беседы"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Получаем статистику беседы
        c.execute('''SELECT users.user_id, users.messages_count, users.level, 
                           users.balance, users.reputation, users.warnings
                    FROM users
                    JOIN message_history ON users.user_id = message_history.user_id
                    WHERE message_history.chat_id = ?
                    GROUP BY users.user_id''', (event.chat_id,))
        
        users_data = c.fetchall()
        
        if not users_data:
            return "❌ Нет данных для экспорта"
            
        # Получаем информацию о пользователях через VK API
        user_ids = [user[0] for user in users_data]
        users_info = vk.users.get(user_ids=user_ids)
        users_dict = {user['id']: user for user in users_info}
        
        # Формируем данные для экспорта
        export_data = {
            'chat_id': event.chat_id,
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'users': []
        }
        
        for user_data in users_data:
            user_id = user_data[0]
            user_info = users_dict.get(user_id, {})
            
            export_data['users'].append({
                'user_id': user_id,
                'name': f"{user_info.get('first_name', 'Unknown')} {user_info.get('last_name', 'User')}",
                'messages': user_data[1],
                'level': user_data[2],
                'balance': user_data[3],
                'reputation': user_data[4],
                'warnings': user_data[5]
            })
        
        # Сохраняем в файл
        filename = f"chat_{event.chat_id}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        return f"📊 Данные экспортированы в файл: {filename}"
        
    except Exception as e:
        log_error(f"Ошибка в команде export: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"
    finally:
        if conn:
            conn.close()

def cmd_welcome(vk, event, args):
    """Управление приветственным сообщением"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return ("⚠️ Использование:\n"
                "/welcome set [текст] — установить приветствие\n"
                "/welcome clear — удалить приветствие\n"
                "/welcome show — показать текущее приветствие\n\n"
                "Доступные переменные:\n"
                "{name} — имя пользователя\n"
                "{chat} — название беседы\n"
                "{members} — количество участников")
    
    action = args[0].lower()
    
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        if action == "set":
            if len(args) < 2:
                return "⚠️ Укажите текст приветствия"
                
            welcome_text = ' '.join(args[1:])
            c.execute('''UPDATE chat_settings 
                        SET welcome_message = ?
                        WHERE chat_id = ?''', (welcome_text, event.chat_id))
            
            if c.rowcount == 0:
                c.execute('''INSERT INTO chat_settings 
                            (chat_id, welcome_message)
                            VALUES (?, ?)''', (event.chat_id, welcome_text))
            
            conn.commit()
            return "✅ Приветственное сообщение установлено"
            
        elif action == "clear":
            c.execute('''UPDATE chat_settings 
                        SET welcome_message = NULL
                        WHERE chat_id = ?''', (event.chat_id,))
            conn.commit()
            return "✅ Приветственное сообщение удалено"
            
        elif action == "show":
            c.execute('''SELECT welcome_message 
                        FROM chat_settings 
                        WHERE chat_id = ?''', (event.chat_id,))
            result = c.fetchone()
            
            if not result or not result[0]:
                return "📝 Приветственное сообщение не установлено"
                
            return f"📝 Текущее приветствие:\n\n{result[0]}"
            
        else:
            return "⚠️ Неверная команда"
            
    except Exception as e:
        log_error(f"Ошибка в команде welcome: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"
    finally:
        if conn:
            conn.close()

def cmd_backup(vk, event, args):
    """Управление резервными копиями беседы"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return ("⚠️ Использование:\n"
                "/backup create — создать резервную копию\n"
                "/backup list — список копий\n"
                "/backup restore [ID] — восстановить из копии")
    
    action = args[0].lower()
    backup_dir = "backups"
    
    try:
        # Создаем директорию для бэкапов, если её нет
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        if action == "create":
            conn = sqlite3.connect('bot.db')
            c = conn.cursor()
            
            # Получаем настройки и данные беседы
            c.execute('''SELECT * FROM chat_settings WHERE chat_id = ?''', (event.chat_id,))
            settings = c.fetchone()
            
            c.execute('''SELECT * FROM word_filters WHERE chat_id = ?''', (event.chat_id,))
            filters = c.fetchall()
            
            backup_data = {
                'chat_id': event.chat_id,
                'backup_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'settings': settings,
                'filters': filters
            }
            
            # Создаем файл бэкапа
            backup_file = f"{backup_dir}/chat_{event.chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
                
            return f"✅ Резервная копия создана: {os.path.basename(backup_file)}"
            
        elif action == "list":
            # Получаем список файлов бэкапов для этой беседы
            backup_files = [f for f in os.listdir(backup_dir) 
                          if f.startswith(f"chat_{event.chat_id}_")]
            
            if not backup_files:
                return "📝 Резервные копии не найдены"
                
            message = "📝 Список резервных копий:\n\n"
            for i, file in enumerate(sorted(backup_files, reverse=True)):
                backup_date = file.split('_')[-1].replace('.json', '')
                message += f"{i+1}. {backup_date}\n"
            return message
            
        elif action == "restore" and len(args) > 1:
            try:
                backup_index = int(args[1]) - 1
                backup_files = sorted([f for f in os.listdir(backup_dir) 
                                    if f.startswith(f"chat_{event.chat_id}_")],
                                    reverse=True)
                
                if not backup_files:
                    return "❌ Резервные копии не найдены"
                    
                if backup_index < 0 or backup_index >= len(backup_files):
                    return "❌ Неверный номер резервной копии"
                    
                backup_file = os.path.join(backup_dir, backup_files[backup_index])
                
                with open(backup_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                
                conn = sqlite3.connect('bot.db')
                c = conn.cursor()
                
                # Восстанавливаем настройки
                if backup_data.get('settings'):
                    c.execute('''INSERT OR REPLACE INTO chat_settings 
                                (chat_id, quiet_mode, welcome_message, auto_warn, max_warnings)
                                VALUES (?, ?, ?, ?, ?)''', backup_data['settings'])
                
                # Восстанавливаем фильтры
                if backup_data.get('filters'):
                    c.execute('DELETE FROM word_filters WHERE chat_id = ?', (event.chat_id,))
                    c.executemany('''INSERT INTO word_filters 
                                    (chat_id, word, added_by, added_time)
                                    VALUES (?, ?, ?, ?)''', backup_data['filters'])
                
                conn.commit()
                return "✅ Настройки беседы восстановлены из резервной копии"
                
            except ValueError:
                return "❌ Укажите корректный номер резервной копии"
        else:
            return "⚠️ Неверная команда"
            
    except Exception as e:
        log_error(f"Ошибка в команде backup: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"
    finally:
        if 'conn' in locals():
            conn.close()

def cmd_automod(vk, event, args):
    """Управление автомодерацией"""
    if not is_admin(event.obj.message['from_id']):
        return "⚠️ У вас нет прав администратора"
        
    if not args:
        return ("⚠️ Использование:\n"
                "/automod status — текущие настройки\n"
                "/automod spam [on/off] — фильтр спама\n"
                "/automod caps [on/off] — фильтр капса\n"
                "/automod links [on/off] — фильтр ссылок\n"
                "/automod warns [число] — макс. предупреждений\n"
                "/automod action [warn/kick/ban] — действие при нарушении")
    
    action = args[0].lower()
    
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Создаем таблицу настроек автомодерации, если её нет
        c.execute('''CREATE TABLE IF NOT EXISTS automod_settings
                    (chat_id INTEGER PRIMARY KEY,
                     spam_filter INTEGER DEFAULT 0,
                     caps_filter INTEGER DEFAULT 0,
                     links_filter INTEGER DEFAULT 0,
                     max_warns INTEGER DEFAULT 3,
                     action TEXT DEFAULT 'warn')''')
        
        # Проверяем существование настроек
        c.execute('''INSERT OR IGNORE INTO automod_settings (chat_id)
                    VALUES (?)''', (event.chat_id,))
        
        if action == "status":
            c.execute('''SELECT spam_filter, caps_filter, links_filter,
                               max_warns, action
                        FROM automod_settings
                        WHERE chat_id = ?''', (event.chat_id,))
            settings = c.fetchone()
            
            return (f"⚙️ Настройки автомодерации:\n\n"
                   f"🚫 Фильтр спама: {'Включен' if settings[0] else 'Выключен'}\n"
                   f"🔠 Фильтр капса: {'Включен' if settings[1] else 'Выключен'}\n"
                   f"🔗 Фильтр ссылок: {'Включен' if settings[2] else 'Выключен'}\n"
                   f"⚠️ Макс. предупреждений: {settings[3]}\n"
                   f"👮 Действие при нарушении: {settings[4]}")
        
        elif action in ["spam", "caps", "links"] and len(args) > 1:
            value = 1 if args[1].lower() == "on" else 0
            column = f"{action}_filter"
            
            c.execute(f'''UPDATE automod_settings 
                         SET {column} = ?
                         WHERE chat_id = ?''', (value, event.chat_id))
            
            conn.commit()
            return f"✅ Фильтр {action} {'включен' if value else 'выключен'}"
        
        elif action == "warns" and len(args) > 1:
            try:
                max_warns = int(args[1])
                if max_warns < 1 or max_warns > 10:
                    return "⚠️ Количество предупреждений должно быть от 1 до 10"
                    
                c.execute('''UPDATE automod_settings 
                            SET max_warns = ?
                            WHERE chat_id = ?''', (max_warns, event.chat_id))
                
                conn.commit()
                return f"✅ Установлено максимальное количество предупреждений: {max_warns}"
            except ValueError:
                return "⚠️ Укажите корректное число предупреждений"
        
        elif action == "action" and len(args) > 1:
            new_action = args[1].lower()
            if new_action not in ["warn", "kick", "ban"]:
                return "⚠️ Доступные действия: warn, kick, ban"
                
            c.execute('''UPDATE automod_settings 
                        SET action = ?
                        WHERE chat_id = ?''', (new_action, event.chat_id))
            
            conn.commit()
            return f"✅ Установлено действие при нарушении: {new_action}"
        
        else:
            return "⚠️ Неверная команда"
            
    except Exception as e:
        log_error(f"Ошибка в команде automod: {str(e)}", exc_info=True)
        return f"❌ Ошибка: {str(e)}"
    finally:
        if conn:
            conn.close() 