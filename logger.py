import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger():
    # Создаем директорию для логов, если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Настраиваем основной логгер
    logger = logging.getLogger('bot')
    logger.setLevel(logging.INFO)

    # Создаем форматтер для логов
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Хендлер для файла (с ротацией)
    file_handler = RotatingFileHandler(
        f'logs/bot.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Хендлер для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# Создаем отдельный логгер для команд
def setup_command_logger():
    logger = logging.getLogger('commands')
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(message)s')

    file_handler = RotatingFileHandler(
        f'logs/commands.log',
        maxBytes=5*1024*1024,
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Функция для логирования команд
def log_command(user_id, chat_id, command, args=None):
    logger = logging.getLogger('commands')
    args_str = ' '.join(args) if args else ''
    logger.info(f'User: {user_id} | Chat: {chat_id} | Command: {command} | Args: {args_str}')

# Функция для логирования ошибок
def log_error(error_msg, exc_info=None):
    logger = logging.getLogger('bot')
    logger.error(error_msg, exc_info=exc_info)

# Функция для логирования действий модерации
def log_moderation(moderator_id, action, target_id, reason=None):
    logger = logging.getLogger('bot')
    log_msg = f'Moderation: {action} | Moderator: {moderator_id} | Target: {target_id}'
    if reason:
        log_msg += f' | Reason: {reason}'
    logger.info(log_msg) 