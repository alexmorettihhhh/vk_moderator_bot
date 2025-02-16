import threading
import time
from datetime import datetime, timedelta
from database import db
from logger import log_error
import logging

# Получаем существующий логгер
logger = logging.getLogger('bot')

def cleanup_old_data():
    """Очистка старых данных"""
    try:
        # Удаляем сообщения старше 30 дней
        thirty_days_ago = datetime.now() - timedelta(days=30)
        db.execute('''DELETE FROM message_history 
                     WHERE timestamp < ?''', (thirty_days_ago,))
        
        # Удаляем истекшие муты
        db.execute('''UPDATE users 
                     SET is_muted = 0, mute_end = NULL 
                     WHERE is_muted = 1 AND mute_end < ?''', 
                     (datetime.now(),))
        
        # Удаляем истекший режим тишины
        db.execute('''UPDATE chat_settings 
                     SET quiet_mode = 0, quiet_end = NULL 
                     WHERE quiet_mode = 1 AND quiet_end < ?''',
                     (datetime.now(),))
        
        logger.info("Очистка старых данных выполнена успешно")
    except Exception as e:
        log_error(f"Ошибка при очистке старых данных: {str(e)}", exc_info=True)

def optimize_database():
    """Оптимизация базы данных"""
    try:
        db.execute('VACUUM')
        db.execute('ANALYZE')
        logger.info("Оптимизация базы данных выполнена успешно")
    except Exception as e:
        log_error(f"Ошибка при оптимизации базы данных: {str(e)}", exc_info=True)

def create_scheduled_backup():
    """Создание регулярного бэкапа"""
    try:
        if db.backup_database():
            logger.info("Регулярный бэкап создан успешно")
        else:
            logger.error("Не удалось создать регулярный бэкап")
    except Exception as e:
        log_error(f"Ошибка при создании регулярного бэкапа: {str(e)}", exc_info=True)

def maintenance_worker():
    """Рабочий процесс обслуживания"""
    while True:
        try:
            # Очистка старых данных каждые 6 часов
            cleanup_old_data()
            
            # Оптимизация базы данных каждые 6 часов
            optimize_database()
            
            # Создание бэкапа каждые 6 часов
            create_scheduled_backup()
            
            # Ждем 6 часов
            time.sleep(6 * 60 * 60)
            
        except Exception as e:
            log_error(f"Ошибка в процессе обслуживания: {str(e)}", exc_info=True)
            time.sleep(300)  # Ждем 5 минут при ошибке

def start_maintenance():
    """Запуск процесса обслуживания"""
    maintenance_thread = threading.Thread(target=maintenance_worker, daemon=True)
    maintenance_thread.start()
    logger.info("Процесс обслуживания базы данных запущен") 