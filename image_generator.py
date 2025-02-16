from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
from datetime import datetime
import requests
from io import BytesIO
import numpy as np

class StatsImageGenerator:
    def __init__(self):
        fonts_dir = "fonts"
        if not os.path.exists(fonts_dir):
            os.makedirs(fonts_dir)
            
        # Улучшенные размеры шрифтов
        self.font_regular = ImageFont.truetype(f"{fonts_dir}/Roboto-Regular.ttf", 20)
        self.font_bold = ImageFont.truetype(f"{fonts_dir}/Roboto-Bold.ttf", 24)
        self.font_title = ImageFont.truetype(f"{fonts_dir}/Roboto-Bold.ttf", 48)
        
        # Современная цветовая схема
        self.colors = {
            'background_start': (22, 27, 34),      # Темный синий
            'background_end': (35, 41, 54),        # Светлее синий
            'text': (255, 255, 255),              # Чистый белый
            'secondary': (179, 186, 197),         # Светло-серый
            'card': (47, 54, 71, 240),           # Полупрозрачный синий
            'card_highlight': (55, 62, 78, 240),  # Подсвеченная карточка
            'accent1': (88, 166, 255),           # Яркий голубой
            'accent2': (255, 122, 155),          # Розовый
            'accent3': (130, 255, 178),          # Мятный
            'gradient1': (88, 166, 255),         # Градиент начало
            'gradient2': (255, 122, 155),        # Градиент конец
            'shadow': (0, 0, 0, 100)             # Тень
        }

    def create_circular_avatar(self, avatar_img, size):
        """Создает круглую аватарку с улучшенным качеством"""
        try:
            # Создаем маску с сглаживанием
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            
            # Изменяем размер аватарки с высоким качеством
            avatar = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Применяем размытие по краям для сглаживания
            mask = mask.filter(ImageFilter.GaussianBlur(1))
            
            # Создаем выходное изображение
            output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            output.paste(avatar, (0, 0))
            output.putalpha(mask)
            
            return output
        except Exception as e:
            print(f"Ошибка при создании круглой аватарки: {str(e)}")
            return None

    def get_user_avatar(self, user_id, avatar_url=None):
        """Получает аватарку пользователя"""
        try:
            if avatar_url:
                response = requests.get(avatar_url, timeout=10)
                if response.status_code == 200:
                    # Открываем изображение из байтов
                    avatar = Image.open(BytesIO(response.content))
                    # Конвертируем в RGB если изображение в другом формате
                    if avatar.mode != 'RGB':
                        avatar = avatar.convert('RGB')
                    # Изменяем размер под наш круг
                    avatar = avatar.resize((100, 100), Image.Resampling.LANCZOS)
                    return avatar
        except Exception as e:
            print(f"Ошибка при получении аватарки: {str(e)}")
        return None

    def create_gradient_background(self, width, height):
        """Создает градиентный фон с улучшенным переходом"""
        background = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(background)
        
        for y in range(height):
            progress = y / height
            r = int(self.colors['background_start'][0] + (self.colors['background_end'][0] - self.colors['background_start'][0]) * progress)
            g = int(self.colors['background_start'][1] + (self.colors['background_end'][1] - self.colors['background_start'][1]) * progress)
            b = int(self.colors['background_start'][2] + (self.colors['background_end'][2] - self.colors['background_start'][2]) * progress)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
            
        # Добавляем легкий шум для текстуры
        noise = np.random.randint(0, 10, (height, width, 3), dtype=np.uint8)
        noise_image = Image.fromarray(noise)
        background = Image.blend(background, noise_image, 0.02)
        
        return background

    def draw_rounded_rectangle(self, draw, xy, radius, fill, shadow=False):
        """Рисует прямоугольник с закругленными углами и тенью"""
        x1, y1, x2, y2 = xy
        
        # Если нужна тень, рисуем её
        if shadow:
            shadow_offset = 4
            shadow_radius = radius + 2
            shadow_fill = self.colors['shadow']
            # Рисуем тень с небольшим смещением
            self._draw_rounded_rectangle_path(draw, 
                                           (x1 + shadow_offset, y1 + shadow_offset, 
                                            x2 + shadow_offset, y2 + shadow_offset),
                                           shadow_radius, shadow_fill)
        
        # Рисуем основной прямоугольник
        self._draw_rounded_rectangle_path(draw, xy, radius, fill)

    def _draw_rounded_rectangle_path(self, draw, xy, radius, fill):
        """Вспомогательный метод для отрисовки закругленного прямоугольника"""
        x1, y1, x2, y2 = xy
        width = x2 - x1
        height = y2 - y1
        
        # Убеждаемся, что радиус не превышает размеры
        radius = min(radius, width//2, height//2)
        
        # Рисуем углы
        draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
        draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
        draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
        draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)
        
        # Рисуем прямоугольники
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

    def draw_stat_card(self, draw, x, y, width, height, title, value, icon_text, accent_color, center_text=False):
        """Рисует улучшенную карточку статистики"""
        # Рисуем карточку с тенью
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), 12, self.colors['card'], shadow=True)
        
        # Добавляем градиентную полоску сверху
        gradient_height = 4
        for i in range(gradient_height):
            progress = i / gradient_height
            color = tuple(int(accent_color[j] * (1 - progress) + self.colors['card'][j] * progress) for j in range(3))
            draw.line([(x, y + i), (x + width, y + i)], fill=color)
        
        if center_text:
            # Центрированный текст для роли
            # Заголовок с тенью
            draw.text((x + width//2 + 1, y + height//3 + 1), title, 
                     font=self.font_regular, fill=self.colors['shadow'], anchor="mm")
            draw.text((x + width//2, y + height//3), title, 
                     font=self.font_regular, fill=self.colors['secondary'], anchor="mm")
            
            # Значение с тенью
            draw.text((x + width//2 + 1, y + height*2//3 + 1), str(value), 
                     font=self.font_bold, fill=self.colors['shadow'], anchor="mm")
            draw.text((x + width//2, y + height*2//3), str(value), 
                     font=self.font_bold, fill=self.colors['text'], anchor="mm")
        else:
            # Стандартное отображение с иконкой слева
            # Отступы и размеры
            padding = 20
            icon_size = height - padding * 2
            
            # Рисуем иконку с эффектом свечения
            icon_font = ImageFont.truetype("fonts/Roboto-Bold.ttf", icon_size)
            # Свечение
            for offset in range(3, 0, -1):
                glow_color = tuple(list(accent_color) + [50])
                draw.text((x + padding + offset, y + height//2), icon_text, 
                         font=icon_font, fill=glow_color, anchor="lm")
            # Основная иконка
            draw.text((x + padding, y + height//2), icon_text, 
                     font=icon_font, fill=accent_color, anchor="lm")
            
            # Позиция текста
            text_x = x + padding + icon_size + padding
            
            # Заголовок с тенью
            draw.text((text_x + 1, y + height//3 + 1), title, 
                     font=self.font_regular, fill=self.colors['shadow'], anchor="lm")
            draw.text((text_x, y + height//3), title, 
                     font=self.font_regular, fill=self.colors['secondary'], anchor="lm")
            
            # Значение с тенью
            draw.text((text_x + 1, y + height*2//3 + 1), str(value), 
                     font=self.font_bold, fill=self.colors['shadow'], anchor="lm")
            draw.text((text_x, y + height*2//3), str(value), 
                     font=self.font_bold, fill=self.colors['text'], anchor="lm")

    def draw_info_block(self, draw, x, y, width, height, user_data):
        """Рисует улучшенный информационный блок"""
        # Рисуем основной блок с тенью
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), 15, self.colors['card'], shadow=True)
        
        # Улучшенные отступы и интервалы
        padding = 25
        line_height = 55
        icon_offset = 45
        
        # Функция для отрисовки строки с иконкой
        def draw_info_line(pos_y, icon, label, value, icon_color):
            # Рисуем иконку с эффектом свечения
            for offset in range(3, 0, -1):
                glow_color = tuple(list(icon_color) + [50])
                draw.text((x + padding + offset, pos_y), icon, 
                         font=self.font_bold, fill=glow_color)
            draw.text((x + padding, pos_y), icon, 
                     font=self.font_bold, fill=icon_color)
            
            # Рисуем метку и значение
            draw.text((x + padding + icon_offset, pos_y), label,
                     font=self.font_regular, fill=self.colors['secondary'])
            draw.text((x + padding + icon_offset, pos_y + 25), value,
                     font=self.font_bold, fill=self.colors['text'])
        
        # Получаем количество сообщений
        messages_count = user_data.get('messages_count', 0)
        
        # Форматирование даты регистрации
        reg_date = user_data.get('reg_date', '')
        if isinstance(reg_date, str):
            try:
                if 'T' in reg_date:
                    reg_date = datetime.strptime(reg_date, '%Y-%m-%dT%H:%M:%S')
                elif '.' in reg_date:
                    reg_date = datetime.strptime(reg_date, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    reg_date = datetime.strptime(reg_date, '%Y-%m-%d %H:%M:%S')
                reg_date = reg_date.strftime('%d.%m.%Y %H:%M')
            except ValueError:
                reg_date = 'Неизвестно'
        elif isinstance(reg_date, datetime):
            reg_date = reg_date.strftime('%d.%m.%Y %H:%M')
        else:
            reg_date = 'Неизвестно'
        
        # Форматирование последней активности
        last_activity = user_data.get('last_activity', datetime.now())
        if isinstance(last_activity, str):
            try:
                if 'T' in last_activity:
                    last_activity = datetime.strptime(last_activity, '%Y-%m-%dT%H:%M:%S')
                elif '.' in last_activity:
                    last_activity = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    last_activity = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
                last_activity = last_activity.strftime('%d.%m.%Y %H:%M')
            except ValueError:
                last_activity = datetime.now().strftime('%d.%m.%Y %H:%M')
        elif isinstance(last_activity, datetime):
            last_activity = last_activity.strftime('%d.%m.%Y %H:%M')
        else:
            last_activity = datetime.now().strftime('%d.%m.%Y %H:%M')
        
        # Отрисовка информационных строк
        draw_info_line(y + padding, "💬", "Сообщений", 
                      str(messages_count), self.colors['accent1'])
        draw_info_line(y + padding + line_height, "📅", "Регистрация",
                      reg_date, self.colors['accent2'])
        draw_info_line(y + padding + line_height * 2, "⌚", "Активность",
                      last_activity, self.colors['accent3'])
        draw_info_line(y + padding + line_height * 3, "👥", "Пригласил",
                      f"{user_data.get('invited_count', 0)} чел.", self.colors['gradient1'])

    def get_role_display_name(self, role):
        """Возвращает отображаемое имя роли с эмодзи"""
        role_names = {
            'admin': '👑 Администратор',
            'senior_moderator': '⭐ Старший Модератор',
            'moder': '🛡️ Модератор',
            'user': '👤 Пользователь'
        }
        return role_names.get(role.lower(), role)

    def draw_role_card(self, draw, x, y, width, height, role_name, role_color):
        """Рисует улучшенную карточку роли"""
        # Рисуем основную карточку с тенью
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), 15, self.colors['card'], shadow=True)
        
        # Добавляем градиентную полоску сверху
        gradient_height = 4
        for i in range(gradient_height):
            progress = i / gradient_height
            color = tuple(int(role_color[j] * (1 - progress) + self.colors['card'][j] * progress) for j in range(3))
            draw.line([(x, y + i), (x + width, y + i)], fill=color)
        
        # Рисуем заголовок "РОЛЬ" с эффектом свечения
        title_y = y + 25
        title = "РОЛЬ"
        # Свечение
        for offset in range(3, 0, -1):
            glow_color = (*role_color[:3], 50)
            draw.text((x + width//2 + offset, title_y + offset), title,
                     font=self.font_regular, fill=glow_color, anchor="mm")
        # Основной текст
        draw.text((x + width//2, title_y), title,
                 font=self.font_regular, fill=self.colors['secondary'], anchor="mm")
        
        # Рисуем значение роли с эффектом свечения
        value_y = y + height - 30
        # Свечение
        for offset in range(3, 0, -1):
            glow_color = (*role_color[:3], 50)
            draw.text((x + width//2 + offset, value_y + offset), role_name,
                     font=self.font_bold, fill=glow_color, anchor="mm")
        # Основной текст
        draw.text((x + width//2, value_y), role_name,
                 font=self.font_bold, fill=role_color, anchor="mm")

    def create_stats_image(self, user_data):
        try:
            # Увеличенные размеры для лучшего качества
            width = 900
            height = 500
            
            # Создаем фон
            image = self.create_gradient_background(width, height)
            draw = ImageDraw.Draw(image)
            
            # Заголовок с эффектом свечения
            title_y = 40
            # Свечение
            for offset in range(4, 0, -1):
                glow_color = (*self.colors['accent1'][:3], 50)
                draw.text((width//2 + offset, title_y + offset), "СТАТИСТИКА",
                         font=self.font_title, fill=glow_color, anchor="mm")
            # Основной текст
            draw.text((width//2, title_y), "СТАТИСТИКА",
                     font=self.font_title, fill=self.colors['text'], anchor="mm")
            
            # Декоративная линия под заголовком
            line_y = title_y + 35
            line_width = 240
            line_height = 4
            for i in range(line_height):
                progress = i / line_height
                color = tuple(int(self.colors['gradient1'][j] * (1 - progress) + 
                                self.colors['gradient2'][j] * progress) for j in range(3))
                draw.line([(width//2 - line_width//2, line_y + i),
                          (width//2 + line_width//2, line_y + i)], fill=color)
            
            # Информационный блок (слева)
            info_block_width = 340
            info_block_height = 280
            self.draw_info_block(draw, 50, 100, info_block_width, info_block_height, user_data)
            
            # Аватар (по центру)
            center_x = width // 2 + 70
            center_y = height // 2 - 60
            avatar_size = 120
            
            # Рисуем круги вокруг аватара
            for i in range(12, 0, -1):
                alpha = int(150 - i * 10)
                if alpha > 0:
                    draw.ellipse(
                        [center_x - avatar_size//2 - i*2, center_y - avatar_size//2 - i*2,
                         center_x + avatar_size//2 + i*2, center_y + avatar_size//2 + i*2],
                        outline=(*self.colors['accent1'][:3], alpha), width=2
                    )
            
            # Вставляем аватар
            if 'avatar_url' in user_data:
                avatar = self.get_user_avatar(user_data['user_id'], user_data['avatar_url'])
                if avatar:
                    circular_avatar = self.create_circular_avatar(avatar, avatar_size)
                    if circular_avatar:
                        image.paste(circular_avatar, 
                                  (center_x - avatar_size//2, center_y - avatar_size//2),
                                  circular_avatar)
            
            # Правая секция
            x_right = width - 340
            
            # Уровень
            level_y = 120
            level_text = str(user_data.get('level', 1))
            # Свечение для текста уровня
            for offset in range(3, 0, -1):
                glow_color = (*self.colors['accent1'][:3], 50)
                draw.text((x_right + 160 + offset, level_y + offset),
                         f"УРОВЕНЬ {level_text}", 
                         font=self.font_bold, fill=glow_color, anchor="mm")
            draw.text((x_right + 160, level_y), f"УРОВЕНЬ {level_text}", 
                     font=self.font_bold, fill=self.colors['text'], anchor="mm")
            
            # XP-бар с улучшенным дизайном
            xp = user_data.get('xp', 0)
            max_xp = user_data.get('level', 1) * 1000
            xp_percentage = min(xp / max_xp, 1) if max_xp > 0 else 0
            bar_width = 220
            bar_height = 10
            
            # Фон XP-бара
            bar_x = x_right + 50
            bar_y = level_y + 35
            self.draw_rounded_rectangle(draw,
                                     (bar_x, bar_y,
                                      bar_x + bar_width, bar_y + bar_height),
                                     5, self.colors['card_highlight'])
            
            # Заполненная часть XP-бара с градиентом
            if xp_percentage > 0:
                fill_width = int(bar_width * xp_percentage)
                if fill_width > 0:
                    for i in range(bar_height):
                        progress = i / bar_height
                        color = tuple(int(self.colors['gradient1'][j] * (1 - progress) + 
                                        self.colors['gradient2'][j] * progress) for j in range(3))
                        draw.line([(bar_x, bar_y + i),
                                 (bar_x + fill_width, bar_y + i)], fill=color)
            
            # XP текст с тенью
            draw.text((x_right + 160, bar_y + 25),
                     f"{xp}/{max_xp} XP",
                     font=self.font_regular, fill=self.colors['secondary'], anchor="mm")
            
            # Роль
            role_y = level_y + 145
            role = self.get_role_display_name(user_data.get('role', 'user'))
            role_color = self.colors['text']
            self.draw_stat_card(draw, x_right + 40, role_y, 246, 80,
                              "Роль", role, "👑", role_color, center_text=True)
            
            # Сохраняем изображение
            os.makedirs("temp", exist_ok=True)
            image_path = f"temp/stats_{user_data['user_id']}.png"
            image = image.convert('RGB')
            image.save(image_path, quality=95)
            return image_path
        except Exception as e:
            print(f"Ошибка при создании изображения статистики: {str(e)}")
            return None

def generate_stats_image(user_data):
    """Создает изображение статистики для пользователя"""
    generator = StatsImageGenerator()
    return generator.create_stats_image(user_data) 