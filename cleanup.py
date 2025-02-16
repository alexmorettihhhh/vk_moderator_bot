import sqlite3
from datetime import datetime, timedelta
from logger import log_error

def cleanup_database():
    """
    Очищает старые записи из базы данных
    """
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()

        # Текущее время
        current_time = datetime.now()

        # Очистка истории предупреждений старше 30 дней
        thirty_days_ago = current_time - timedelta(days=30)
        c.execute('DELETE FROM warn_history WHERE timestamp < ?', (thirty_days_ago,))

        # Очистка истории репутации старше 90 дней
        ninety_days_ago = current_time - timedelta(days=90)
        c.execute('DELETE FROM reputation_history WHERE timestamp < ?', (ninety_days_ago,))

        # Очистка обработанных баг-репортов старше 30 дней
        c.execute('''DELETE FROM bug_reports 
                    WHERE status != 'new' 
                    AND report_time < ?''', (thirty_days_ago,))

        # Очистка записей о мутах, срок которых истек
        c.execute('''UPDATE users 
                    SET is_muted = 0, mute_end = NULL 
                    WHERE is_muted = 1 
                    AND mute_end < ?''', (current_time,))

        # Очистка режима тишины, срок которого истек
        c.execute('''UPDATE chat_settings 
                    SET quiet_mode = 0, quiet_end = NULL 
                    WHERE quiet_mode = 1 
                    AND quiet_end < ?''', (current_time,))

        # Очистка неактивных бесед (не было активности более 30 дней)
        c.execute('''UPDATE bot_chats 
                    SET is_active = 0 
                    WHERE last_activity < ?''', (thirty_days_ago,))

        # Сохраняем изменения
        conn.commit()

        # Оптимизация базы данных
        c.execute('VACUUM')
        
        conn.close()
        return True

    except Exception as e:
        log_error(f"Ошибка при очистке базы данных: {str(e)}", exc_info=True)
        return False

def cleanup_inactive_users():
    """
    Очищает данные неактивных пользователей
    """
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()

        # Получаем список всех пользователей
        c.execute('SELECT user_id, last_activity FROM users')
        users = c.fetchall()

        # Текущее время
        current_time = datetime.now()
        ninety_days_ago = current_time - timedelta(days=90)

        for user_id, last_activity in users:
            if last_activity and datetime.fromisoformat(last_activity) < ninety_days_ago:
                # Сбрасываем статистику неактивного пользователя
                c.execute('''UPDATE users 
                            SET messages_count = 0,
                                level = 1,
                                xp = 0,
                                balance = 0,
                                reputation = 0
                            WHERE user_id = ?''', (user_id,))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        log_error(f"Ошибка при очистке неактивных пользователей: {str(e)}", exc_info=True)
        return False

def schedule_cleanup():
    """
    Планирует регулярную очистку базы данных
    """
    import schedule
    import time

    # Очистка базы данных каждый день в 3:00
    schedule.every().day.at("03:00").do(cleanup_database)
    
    # Очистка неактивных пользователей каждую неделю в воскресенье в 4:00
    schedule.every().sunday.at("04:00").do(cleanup_inactive_users)

    while True:
        schedule.run_pending()
        time.sleep(60) 