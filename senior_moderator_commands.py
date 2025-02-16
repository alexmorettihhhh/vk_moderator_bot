import sqlite3
from datetime import datetime
from vk_api.utils import get_random_id
from utils import extract_user_id

def cmd_ban(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя и причину"
    
    try:
        target = args[0]
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
            
        reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"
        chat_id = event.chat_id
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''INSERT INTO bans (user_id, chat_id, ban_time)
                    VALUES (?, ?, ?)''', (user_id, chat_id, datetime.now()))
        
        conn.commit()
        conn.close()
        
        # Kick user from chat
        vk.messages.removeChatUser(
            chat_id=chat_id,
            user_id=user_id
        )
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"🚫 Пользователь @id{user_id} ({user_info['first_name']}) заблокирован\nПричина: {reason}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_unban(vk, event, args):
    if not args:
        return "⚠️ Укажите пользователя"
    
    try:
        target = ' '.join(args)
        user_id = extract_user_id(vk, target)
        if not user_id:
            return "❌ Не удалось определить пользователя"
            
        chat_id = event.chat_id
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # Проверяем, забанен ли пользователь
        c.execute('SELECT ban_time FROM bans WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
        ban = c.fetchone()
        
        if not ban:
            conn.close()
            user_info = vk.users.get(user_ids=[user_id])[0]
            return f"⚠️ Пользователь @id{user_id} ({user_info['first_name']}) не находится в бане"
        
        c.execute('''DELETE FROM bans 
                    WHERE user_id = ? AND chat_id = ?''', (user_id, chat_id))
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ Пользователь @id{user_id} ({user_info['first_name']}) разблокирован"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_addmoder(vk, event, args):
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
                    VALUES (?, 'moderator')''', (user_id,))
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ Пользователю @id{user_id} ({user_info['first_name']}) выдана роль модератора"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_removerole(vk, event, args):
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
                    SET role = 'user' 
                    WHERE user_id = ?''', (user_id,))
        
        conn.commit()
        conn.close()
        
        user_info = vk.users.get(user_ids=[user_id])[0]
        return f"✅ У пользователя @id{user_id} ({user_info['first_name']}) забрана роль"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_zov(vk, event):
    try:
        chat_members = vk.messages.getConversationMembers(
            peer_id=2000000000 + event.chat_id
        )
        
        mentions = []
        for member in chat_members['profiles']:
            mentions.append(f"@id{member['id']} ({member['first_name']})")
        
        return "🔔 Всеобщий призыв!\n" + ", ".join(mentions)
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_online(vk, event):
    try:
        chat_members = vk.messages.getConversationMembers(
            peer_id=2000000000 + event.chat_id
        )
        
        online_members = []
        for member in chat_members['profiles']:
            if member.get('online', 0) == 1:
                online_members.append(f"@id{member['id']} ({member['first_name']})")
        
        if not online_members:
            return "😴 Сейчас никого нет онлайн"
        
        return "🟢 Сейчас онлайн:\n" + ", ".join(online_members)
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_banlist(vk, event):
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        c.execute('''SELECT user_id, ban_time 
                    FROM bans 
                    WHERE chat_id = ? 
                    ORDER BY ban_time DESC''', (event.chat_id,))
        bans = c.fetchall()
        conn.close()
        
        if not bans:
            return "✅ В этой беседе нет заблокированных пользователей"
        
        message = "📋 Список заблокированных пользователей:\n"
        for user_id, ban_time in bans:
            message += f"• {user_id}: с {ban_time}\n"
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def cmd_onlinelist(vk, event):
    try:
        chat_members = vk.messages.getConversationMembers(
            peer_id=2000000000 + event.chat_id
        )
        
        online_count = 0
        message = "📊 Статистика онлайна:\n"
        
        for member in chat_members['profiles']:
            status = "🟢" if member.get('online', 0) == 1 else "⚫"
            message += f"{status} @id{member['id']} ({member['first_name']})\n"
            if member.get('online', 0) == 1:
                online_count += 1
        
        message += f"\nВсего онлайн: {online_count}/{len(chat_members['profiles'])}"
        return message
    except Exception as e:
        return f"❌ Ошибка: {str(e)}" 