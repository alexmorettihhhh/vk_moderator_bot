import time
from collections import defaultdict
from datetime import datetime, timedelta
from logger import log_error, log_moderation
import sqlite3
import re

class AntiSpam:
    def __init__(self):
        # Словарь для хранения времени последних сообщений пользователей
        self.user_messages = defaultdict(list)
        # Словарь для хранения предупреждений пользователей
        self.user_warnings = defaultdict(int)
        # Кэш ролей пользователей
        self.role_cache = {}
        # Время жизни кэша (в секундах)
        self.cache_lifetime = 300  # 5 минут
        # Настройки антиспама
        self.settings = {
            'message_interval': 1.0,  # Минимальный интервал между сообщениями (в секундах)
            'max_messages': 5,  # Максимальное количество сообщений за период
            'check_period': 10,  # Период проверки (в секундах)
            'max_warnings': 3,  # Максимальное количество предупреждений до мута
            'mute_duration': 300,  # Длительность мута (в секундах)
            'max_similar_messages': 3,  # Максимальное количество похожих сообщений
            'similarity_threshold': 0.85,  # Порог схожести сообщений (от 0 до 1)
            'max_caps_percentage': 70,  # Максимальный процент заглавных букв
            'max_links_per_message': 2,  # Максимальное количество ссылок в сообщении
            'max_message_length': 1000  # Максимальная длина сообщения
        }
        # Регулярные выражения для проверки спама
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.invite_link_pattern = re.compile(r'vk\.com/join|vk\.me/join|vk\.cc/')

    def get_user_role(self, user_id):
        """Получает роль пользователя из базы данных с использованием кэша"""
        current_time = time.time()
        
        # Проверяем кэш
        if user_id in self.role_cache:
            cached_role, cache_time = self.role_cache[user_id]
            if current_time - cache_time < self.cache_lifetime:
                return cached_role
        
        try:
            conn = sqlite3.connect('bot.db')
            c = conn.cursor()
            c.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
            result = c.fetchone()
            role = result[0] if result else 'user'
            
            # Обновляем кэш
            self.role_cache[user_id] = (role, current_time)
            
            conn.close()
            return role
        except Exception as e:
            log_error(f"Ошибка при получении роли пользователя: {str(e)}")
            return 'user'

    def clean_old_messages(self, user_id):
        """Очищает старые сообщения пользователя"""
        current_time = time.time()
        self.user_messages[user_id] = [
            msg for msg in self.user_messages[user_id]
            if current_time - msg['time'] <= self.settings['check_period']
        ]

    def calculate_similarity(self, text1, text2):
        """Вычисляет схожесть двух текстов"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def check_message_content(self, message):
        """Проверяет содержимое сообщения на спам"""
        # Проверка на капс
        if len(message) > 10:
            caps_count = sum(1 for c in message if c.isupper())
            if caps_count / len(message) * 100 > self.settings['max_caps_percentage']:
                return True, "слишком много заглавных букв"

        # Проверка на длину сообщения
        if len(message) > self.settings['max_message_length']:
            return True, "сообщение слишком длинное"

        # Проверка на ссылки
        urls = self.url_pattern.findall(message)
        if len(urls) > self.settings['max_links_per_message']:
            return True, "слишком много ссылок"

        # Проверка на инвайт-ссылки
        if self.invite_link_pattern.search(message):
            return True, "обнаружена инвайт-ссылка"

        return False, None

    def is_message_spam(self, user_id, message_text):
        """
        Проверяет, является ли сообщение спамом
        Возвращает (is_spam, reason)
        """
        # Проверяем роль пользователя
        user_role = self.get_user_role(user_id)
        if user_role in ['moderator', 'senior_moderator', 'admin']:
            return False, None

        # Проверка содержимого сообщения
        is_spam, reason = self.check_message_content(message_text)
        if is_spam:
            return True, reason

        current_time = time.time()
        self.clean_old_messages(user_id)

        # Добавляем текущее сообщение
        self.user_messages[user_id].append({
            'text': message_text,
            'time': current_time
        })

        # Проверка интервала между сообщениями
        if len(self.user_messages[user_id]) > 1:
            last_msg_time = self.user_messages[user_id][-2]['time']
            if current_time - last_msg_time < self.settings['message_interval']:
                return True, "слишком частые сообщения"

        # Проверка количества сообщений за период
        if len(self.user_messages[user_id]) > self.settings['max_messages']:
            return True, "слишком много сообщений"

        # Проверка похожих сообщений
        similar_count = 1
        for old_msg in reversed(self.user_messages[user_id][:-1]):
            if self.calculate_similarity(message_text, old_msg['text']) >= self.settings['similarity_threshold']:
                similar_count += 1
                if similar_count > self.settings['max_similar_messages']:
                    return True, "повторяющиеся сообщения"

        return False, None

    def handle_spam(self, vk, chat_id, user_id, reason):
        """Обрабатывает обнаруженный спам"""
        # Проверяем роль пользователя перед выдачей предупреждения
        user_role = self.get_user_role(user_id)
        if user_role in ['moderator', 'senior_moderator', 'admin']:
            return None

        self.user_warnings[user_id] += 1
        warning_count = self.user_warnings[user_id]

        try:
            conn = sqlite3.connect('bot.db')
            c = conn.cursor()
            
            # Логируем предупреждение
            c.execute('''INSERT INTO warn_history (user_id, warned_by, reason, timestamp)
                        VALUES (?, ?, ?, ?)''', 
                        (user_id, 0, f"Антиспам: {reason}", datetime.now()))
            
            if warning_count >= self.settings['max_warnings']:
                # Мутим пользователя
                try:
                    # Добавляем запись о муте
                    mute_end = datetime.now() + timedelta(seconds=self.settings['mute_duration'])
                    c.execute('''UPDATE users 
                                SET is_muted = 1, mute_end = ? 
                                WHERE user_id = ?''', (mute_end, user_id))
                    
                    vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
                    log_moderation('ANTISPAM', 'MUTE', user_id, f"Автоматический мут за спам: {reason}")
                    
                    conn.commit()
                    conn.close()
                    
                    return f"🤖 Пользователь @id{user_id} получил мут на {self.settings['mute_duration'] // 60} минут за спам ({reason})"
                except Exception as e:
                    log_error(f"Ошибка при муте пользователя {user_id}: {str(e)}")
                    return None
            else:
                conn.commit()
                conn.close()
                # Выдаем предупреждение
                return f"⚠️ Пользователь @id{user_id} получает предупреждение за спам ({reason}). {warning_count}/{self.settings['max_warnings']}"
                
        except Exception as e:
            log_error(f"Ошибка при обработке спама: {str(e)}")
            if conn:
                conn.close()
            return None

    def reset_warnings(self, user_id):
        """Сбрасывает предупреждения пользователя"""
        if user_id in self.user_warnings:
            del self.user_warnings[user_id]
        
    def clear_cache(self):
        """Очищает устаревшие данные из кэша ролей"""
        current_time = time.time()
        self.role_cache = {
            user_id: (role, cache_time)
            for user_id, (role, cache_time) in self.role_cache.items()
            if current_time - cache_time < self.cache_lifetime
        }

    def update_settings(self, new_settings):
        """Обновляет настройки антиспама"""
        self.settings.update(new_settings)

# Создаем глобальный экземпляр антиспама
antispam = AntiSpam() 