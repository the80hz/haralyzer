import json
import re
import sqlite3
from haralyzer import HarParser
import requests
import os

# Регулярное выражение для извлечения основной части URL и удаления параметров
PATTERN = r'(https://pbs\.twimg\.com/media/[a-zA-Z0-9_-]+)(\?.*)?'

# Инициализация базы данных SQLite
conn = sqlite3.connect('images.db')
cursor = conn.cursor()

# Создание таблицы для хранения ссылок и их статуса загрузки
cursor.execute('''
CREATE TABLE IF NOT EXISTS images (
    url TEXT PRIMARY KEY,
    downloaded BOOLEAN
)
''')

# Загрузка HAR файла
with open('x.com.har', 'r', encoding='utf-8') as f:
    har_parser = HarParser(json.loads(f.read()))

data = har_parser.har_data["entries"]
image_urls = []

# Обрабатываем все ссылки из HAR файла
for entry in data:
    if entry["response"]["content"]["mimeType"].startswith("image/"):
        image_urls.append(entry["request"]["url"])

# Загрузка и сохранение картинок
for link in image_urls:
    if 'media' in link:
        # Применение регулярного выражения: удаляем старые параметры и добавляем новые
        new_link = re.sub(PATTERN, r'\1?format=jpg&name=4096x4096', link)
        
        # Проверка, есть ли ссылка в базе данных и загружена ли она
        cursor.execute('SELECT downloaded FROM images WHERE url = ?', (new_link,))
        result = cursor.fetchone()

        # Если картинки нет в базе данных или она не загружена, скачиваем её
        if result is None or not result[0]:
            # Скачиваем картинку
            response = requests.get(new_link)
            if response.status_code == 200:
                # Сохраняем картинку в файл
                image_name = os.path.basename(new_link)
                with open(image_name, 'wb') as img_file:
                    img_file.write(response.content)
                
                # Обновляем базу данных
                cursor.execute('''
                INSERT OR REPLACE INTO images (url, downloaded) 
                VALUES (?, ?)
                ''', (new_link, True))
                
                print(f"Downloaded and saved: {new_link}")
            else:
                print(f"Failed to download: {new_link}")
        else:
            print(f"Already downloaded: {new_link}")

# Сохранение изменений и закрытие соединения с базой данных
conn.commit()
conn.close()
