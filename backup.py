import os
import shutil
import sqlite3
from datetime import datetime
import zipfile
from logger import log_error

def create_backup():
    """
    Создает резервную копию базы данных
    """
    try:
        # Создаем директорию для бэкапов, если её нет
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Формируем имя файла бэкапа с текущей датой и временем
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'bot_backup_{current_time}.db'
        backup_path = os.path.join(backup_dir, backup_filename)

        # Создаем копию базы данных
        shutil.copy2('bot.db', backup_path)

        # Создаем ZIP архив
        zip_filename = f'bot_backup_{current_time}.zip'
        zip_path = os.path.join(backup_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_path, backup_filename)

        # Удаляем временный файл .db
        os.remove(backup_path)

        # Очищаем старые бэкапы (оставляем только последние 5)
        cleanup_old_backups(backup_dir)

        return True
    except Exception as e:
        log_error(f"Ошибка при создании бэкапа: {str(e)}", exc_info=True)
        return False

def cleanup_old_backups(backup_dir, keep_count=5):
    """
    Удаляет старые бэкапы, оставляя только последние keep_count файлов
    """
    try:
        # Получаем список всех файлов бэкапов
        backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.zip')]
        backup_files.sort(reverse=True)  # Сортируем по убыванию (новые первые)

        # Удаляем лишние файлы
        for old_file in backup_files[keep_count:]:
            os.remove(os.path.join(backup_dir, old_file))
    except Exception as e:
        log_error(f"Ошибка при очистке старых бэкапов: {str(e)}", exc_info=True)

def restore_backup(backup_file):
    """
    Восстанавливает базу данных из бэкапа
    """
    try:
        # Проверяем существование файла бэкапа
        if not os.path.exists(backup_file):
            raise FileNotFoundError("Файл бэкапа не найден")

        # Создаем временную директорию для распаковки
        temp_dir = 'temp_restore'
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # Распаковываем архив
        with zipfile.ZipFile(backup_file, 'r') as zipf:
            zipf.extractall(temp_dir)

        # Находим файл .db в распакованных файлах
        db_file = next(f for f in os.listdir(temp_dir) if f.endswith('.db'))
        
        # Создаем бэкап текущей базы данных перед восстановлением
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        pre_restore_backup = f'pre_restore_backup_{current_time}.db'
        shutil.copy2('bot.db', pre_restore_backup)

        # Восстанавливаем базу данных
        shutil.copy2(os.path.join(temp_dir, db_file), 'bot.db')

        # Очищаем временные файлы
        shutil.rmtree(temp_dir)
        
        return True
    except Exception as e:
        log_error(f"Ошибка при восстановлении из бэкапа: {str(e)}", exc_info=True)
        # Восстанавливаем оригинальную базу данных в случае ошибки
        if os.path.exists(pre_restore_backup):
            shutil.copy2(pre_restore_backup, 'bot.db')
        return False
    finally:
        # Удаляем временный бэкап
        if os.path.exists(pre_restore_backup):
            os.remove(pre_restore_backup) 