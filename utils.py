import requests
from datetime import datetime
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_user_id(vk, text):
    """Извлекает ID пользователя из текста (поддерживает упоминания и обычные ID)"""
    if not text:
        return None
    
    # Если это упоминание (например, @durov или [id1|Павел])
    if '@' in text or '[' in text:
        # Извлекаем ID из формата [id123|Name]
        import re
        id_match = re.search(r'\[id(\d+)\|.*?\]', text)
        if id_match:
            return int(id_match.group(1))
        
        # Если это @username
        username = text.strip('@')
        try:
            user_info = vk.users.get(user_ids=username)
            if user_info:
                return user_info[0]['id']
        except:
            pass
    
    # Если это просто ID
    try:
        return int(text)
    except ValueError:
        return None

def get_weather(city):
    """Получить погоду для города"""
    API_KEY = os.getenv('OPENWEATHER_API_KEY')
    if not API_KEY:
        return None
        
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=ru"
        response = requests.get(url, timeout=10)  # Добавляем timeout
        data = response.json()
        
        if response.status_code == 200:
            weather = {
                'temp': round(data['main']['temp']),
                'feels_like': round(data['main']['feels_like']),
                'description': data['weather'][0]['description'],
                'humidity': data['main']['humidity'],
                'wind_speed': data['wind']['speed']
            }
            return weather
        return None
    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None

def get_currency_rates():
    """Получить курсы валют"""
    try:
        url = "https://www.cbr-xml-daily.ru/daily_json.js"
        response = requests.get(url, timeout=10)  # Добавляем timeout
        data = response.json()
        
        rates = {
            'USD': round(data['Valute']['USD']['Value'], 2),
            'EUR': round(data['Valute']['EUR']['Value'], 2)
        }
        return rates
    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None

def format_duration(seconds):
    """Форматировать длительность"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}ч")
    if minutes > 0:
        parts.append(f"{minutes}м")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}с")
    
    return " ".join(parts)

def check_achievement(conn, user_id, achievement_type, condition_value, required_value):
    """Проверить и выдать достижение"""
    if condition_value >= required_value:
        c = conn.cursor()
        
        # Проверяем, нет ли уже такого достижения
        c.execute('''SELECT 1 FROM achievements 
                    WHERE user_id = ? AND achievement_type = ?''', 
                    (user_id, achievement_type))
        
        if not c.fetchone():
            c.execute('''INSERT INTO achievements (user_id, achievement_type, achievement_date)
                        VALUES (?, ?, ?)''', (user_id, achievement_type, datetime.now()))
            conn.commit()
            return True
    return False

def get_chat_stats(vk, chat_id):
    """Получить статистику беседы"""
    try:
        members = vk.messages.getConversationMembers(peer_id=2000000000 + chat_id)
        
        stats = {
            'total_members': len(members['profiles']),
            'online_count': sum(1 for m in members['profiles'] if m.get('online', 0) == 1),
            'admins_count': sum(1 for m in members.get('items', []) if m.get('is_admin', False))
        }
        return stats
    except:
        return None

def parse_duration(duration_str):
    """Парсинг строки длительности (например, '1h30m' или '5m')"""
    total_seconds = 0
    current_number = ''
    
    for char in duration_str:
        if char.isdigit():
            current_number += char
        elif char in ['h', 'ч']:
            if current_number:
                total_seconds += int(current_number) * 3600
                current_number = ''
        elif char in ['m', 'м']:
            if current_number:
                total_seconds += int(current_number) * 60
                current_number = ''
        elif char in ['s', 'с']:
            if current_number:
                total_seconds += int(current_number)
                current_number = ''
    
    if current_number:  # Если строка заканчивается числом без единицы измерения
        total_seconds += int(current_number) * 60  # Считаем как минуты по умолчанию
    
    return total_seconds 