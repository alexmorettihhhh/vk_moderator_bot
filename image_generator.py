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
            
        # Уменьшаем размеры шрифтов
        self.font_regular = ImageFont.truetype(f"{fonts_dir}/Roboto-Regular.ttf", 18)
        self.font_bold = ImageFont.truetype(f"{fonts_dir}/Roboto-Bold.ttf", 22)
        self.font_title = ImageFont.truetype(f"{fonts_dir}/Roboto-Bold.ttf", 44)
        
        # Современная цветовая схема с улучшенной контрастностью
        self.colors = {
            'background_start': (17, 23, 35),   # Темно-синий
            'background_end': (25, 35, 55),     # Светло-синий
            'text': (255, 255, 255),           # Белый текст
            'secondary': (200, 210, 230),      # Светло-серый для подписей (увеличена яркость)
            'card': (30, 40, 60, 230),         # Полупрозрачный синий (увеличена непрозрачность)
            'accent1': (88, 101, 242),         # Discord Blurple
            'accent2': (255, 115, 115),        # Коралловый
            'accent3': (87, 242, 135),         # Мятный
            'gradient1': (114, 137, 218),      # Градиент начало
            'gradient2': (255, 122, 122)       # Градиент конец
        }

    def create_circular_avatar(self, avatar_img, size):
        """Создает круглую аватарку"""
        try:
            # Создаем новое изображение с прозрачностью
            mask = Image.new('L', (size, size), 0)
            
            # Рисуем круглую маску
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            
            # Создаем новое RGB изображение
            output = Image.new('RGB', (size, size), (0, 0, 0))
            
            # Изменяем размер аватарки
            avatar = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Применяем маску
            output.paste(avatar, (0, 0), mask)
            
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
        """Создает градиентный фон"""
        background = Image.new('RGB', (width, height))
        for y in range(height):
            r = int(self.colors['background_start'][0] + (self.colors['background_end'][0] - self.colors['background_start'][0]) * y / height)
            g = int(self.colors['background_start'][1] + (self.colors['background_end'][1] - self.colors['background_start'][1]) * y / height)
            b = int(self.colors['background_start'][2] + (self.colors['background_end'][2] - self.colors['background_start'][2]) * y / height)
            for x in range(width):
                background.putpixel((x, y), (r, g, b))
        return background

    def draw_rounded_rectangle(self, draw, xy, radius, fill):
        """Рисует прямоугольник с закругленными углами"""
        x1, y1, x2, y2 = xy
        # Убедимся, что x2 > x1 и y2 > y1
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # Проверяем, что размеры достаточны для радиуса
        width = x2 - x1
        height = y2 - y1
        radius = min(radius, width//2, height//2)
        
        # Рисуем углы
        draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
        draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
        draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
        draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)
        
        # Рисуем прямоугольники
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

    def draw_stat_card(self, draw, x, y, width, height, title, value, icon_text, accent_color):
        """Рисует карточку статистики с иконкой и градиентом"""
        # Рисуем основную карточку
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), 10, self.colors['card'])
        
        # Отступы
        padding = 20
        icon_size = int(height * 0.6)  # Увеличиваем размер иконки
        
        # Добавляем иконку с увеличенным размером шрифта
        icon_font = ImageFont.truetype("fonts/Roboto-Bold.ttf", icon_size)
        draw.text((x + padding, y + height//2), icon_text, 
                 font=icon_font, fill=accent_color, anchor="lm")
        
        # Вычисляем позицию для текста
        text_x = x + padding + icon_size + padding
        
        # Добавляем заголовок (сверху)
        draw.text((text_x, y + height//3), title, 
                 font=self.font_regular, fill=self.colors['secondary'],
                 anchor="lm")
        
        # Добавляем значение (снизу)
        draw.text((text_x, y + height*2//3), str(value), 
                 font=self.font_bold, fill=self.colors['text'],
                 anchor="lm")

    def draw_info_block(self, draw, x, y, width, height, user_data):
        """Рисует блок с дополнительной информацией"""
        # Рисуем основной блок
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), 15, self.colors['card'])

        # Увеличиваем отступы
        padding = 25
        line_height = 50
        icon_offset = 40

        # Сообщения
        draw.text((x + padding, y + padding), "💬", font=self.font_bold, fill=self.colors['text'])
        draw.text((x + padding + icon_offset, y + padding), "Сообщений", font=self.font_regular, fill=self.colors['secondary'])
        draw.text((x + padding + icon_offset, y + padding + 25), str(user_data.get('messages', 0)), font=self.font_bold, fill=self.colors['text'])

        # Дата регистрации
        draw.text((x + padding, y + padding + line_height), "📅", font=self.font_bold, fill=self.colors['text'])
        draw.text((x + padding + icon_offset, y + padding + line_height), "Регистрация", font=self.font_regular, fill=self.colors['secondary'])
        draw.text((x + padding + icon_offset, y + padding + line_height + 25), str(user_data.get('reg_date', '')), font=self.font_bold, fill=self.colors['text'])

        # Последняя активность
        draw.text((x + padding, y + padding + line_height * 2), "⌚", font=self.font_bold, fill=self.colors['text'])
        draw.text((x + padding + icon_offset, y + padding + line_height * 2), "Активность", font=self.font_regular, fill=self.colors['secondary'])
        draw.text((x + padding + icon_offset, y + padding + line_height * 2 + 25), datetime.now().strftime('%d.%m.%Y'), font=self.font_bold, fill=self.colors['text'])

        # Количество приглашенных
        draw.text((x + padding, y + padding + line_height * 3), "👥", font=self.font_bold, fill=self.colors['text'])
        draw.text((x + padding + icon_offset, y + padding + line_height * 3), "Пригласил", font=self.font_regular, fill=self.colors['secondary'])
        draw.text((x + padding + icon_offset, y + padding + line_height * 3 + 25), f"{user_data.get('invited_count', 0)} чел.", font=self.font_bold, fill=self.colors['text'])

    def get_role_display_name(self, role):
        """Возвращает отображаемое имя роли"""
        role_names = {
            'admin': 'Администратор',
            'moder': 'Модератор',
            'senior_moderator': 'Старший Модератор',
            'user': 'Пользователь'
        }
        return role_names.get(role.lower(), role)

    def create_stats_image(self, user_data):
        try:
            width = 850
            height = 450
            image = self.create_gradient_background(width, height)
            draw = ImageDraw.Draw(image)

            # Заголовок
            title_y = 35
            draw.text((width//2, title_y), "СТАТИСТИКА",
                    font=self.font_title, fill=self.colors['text'], anchor="mm")
            draw.line([(width//2 - 120, title_y + 30), (width//2 + 120, title_y + 30)],
                    fill=self.colors['accent1'], width=3)

            # Левая секция (информационный блок)
            info_block_width = 320
            info_block_height = 240
            self.draw_info_block(draw, 50, 100, info_block_width, info_block_height, user_data)

            # Центральная секция (аватар)
            center_x = width // 2 + 70  # Сдвигаем аватар правее
            center_y = height // 2 - 80
            avatar_size = 100

            # Рисуем круглую подложку для аватара
            for i in range(10):
                alpha = int(255 - i * 25)
                if alpha > 0:
                    draw.ellipse(
                        [center_x - avatar_size//2 - i, center_y - avatar_size//2 - i,
                        center_x + avatar_size//2 + i, center_y + avatar_size//2 + i],
                        outline=(88, 101, 242, alpha), width=2
                    )

            # Вставляем аватарку
            if 'avatar_url' in user_data:
                avatar = self.get_user_avatar(user_data['user_id'], user_data['avatar_url'])
                if avatar:
                    try:
                        circular_avatar = self.create_circular_avatar(avatar, avatar_size)
                        if circular_avatar:
                            mask = Image.new('L', (avatar_size, avatar_size), 0)
                            mask_draw = ImageDraw.Draw(mask)
                            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                            image.paste(circular_avatar, 
                                    (center_x - avatar_size//2, center_y - avatar_size//2),
                                    mask)
                    except Exception as e:
                        print(f"Ошибка при вставке аватарки: {str(e)}")

            # Правая секция
            x_right = width - 320

            # Уровень (на месте роли)
            level_y = 120
            level_text = str(user_data.get('level', 1))
            draw.text((x_right + 160, level_y), f"УРОВЕНЬ {level_text}", 
                    font=self.font_bold, fill=self.colors['text'], anchor="mm")

            # XP-бар (под уровнем)
            xp = user_data.get('xp', 0)
            max_xp = user_data.get('level', 1) * 1000
            xp_percentage = min(xp / max_xp, 1) if max_xp > 0 else 0
            bar_width = 200
            bar_height = 8

            # Фон XP-бара
            bar_x = x_right + 60  # Центрируем в правой секции
            bar_y = level_y + 30
            self.draw_rounded_rectangle(draw,
                                    (bar_x, bar_y,
                                     bar_x + bar_width, bar_y + bar_height),
                                    4, self.colors['card'])

            # Заполненная часть XP-бара
            if xp_percentage > 0:
                fill_width = int(bar_width * xp_percentage)
                if fill_width > 0:
                    self.draw_rounded_rectangle(draw,
                                            (bar_x, bar_y,
                                             bar_x + fill_width, bar_y + bar_height),
                                            4, self.colors['accent1'])

            # XP текст
            draw.text((x_right + 160, bar_y + 20),
                    f"{xp}/{max_xp} XP",
                    font=self.font_regular, fill=self.colors['secondary'], anchor="mm")

            # Роль (выше, ближе к уровню)
            role_y = level_y + 145
            role = self.get_role_display_name(user_data.get('role', 'user'))
            role_color = self.colors['accent1'] if user_data.get('role', '').lower() == 'admin' else self.colors['text']
            self.draw_stat_card(draw, x_right + 40, role_y, 246, 70,
                                "Роль", role,
                                "👑", role_color)

            # Сохраняем изображение
            os.makedirs("temp", exist_ok=True)
            image_path = f"temp/stats_{user_data['user_id']}.png"
            image.save(image_path, quality=95)
            return image_path
        except Exception as e:
            print(f"Ошибка при создании изображения статистики: {str(e)}")
            return None

def generate_stats_image(user_data):
    """Создает изображение статистики для пользователя"""
    generator = StatsImageGenerator()
    return generator.create_stats_image(user_data) 