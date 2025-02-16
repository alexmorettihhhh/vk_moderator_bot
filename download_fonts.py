import os
import requests

def download_font(url, filename):
    """Скачивает шрифт по URL и сохраняет его в папку fonts"""
    fonts_dir = "fonts"
    if not os.path.exists(fonts_dir):
        os.makedirs(fonts_dir)
        
    filepath = os.path.join(fonts_dir, filename)
    if not os.path.exists(filepath):
        response = requests.get(url)
        with open(filepath, 'wb') as f:
            f.write(response.content)
        print(f"Скачан шрифт: {filename}")
    else:
        print(f"Шрифт уже существует: {filename}")

def main():
    # URLs для шрифтов Roboto
    fonts = {
        'Roboto-Regular.ttf': 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf',
        'Roboto-Bold.ttf': 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf'
    }
    
    for filename, url in fonts.items():
        download_font(url, filename)

if __name__ == "__main__":
    main() 