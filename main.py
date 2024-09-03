import json
import re
import sqlite3
import requests
import os
import time
import logging
from haralyzer import HarParser

# Настройка логгирования для записи в файл и вывода в консоль
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler('download_images.log'),
                        logging.StreamHandler()
                    ])

# Регулярное выражение для извлечения основной части URL и удаления параметров
PATTERN = r'https://pbs\.twimg\.com/media/([a-zA-Z0-9_-]+)(\?.*)?'

# Папка для сохранения изображений
MEDIA_DIR = 'media'

# Создание папки, если она не существует
if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)

# Инициализация базы данных SQLite
conn = sqlite3.connect('images.db')
cursor = conn.cursor()

# Создание таблицы для хранения идентификаторов картинок и их статуса загрузки
cursor.execute('''
CREATE TABLE IF NOT EXISTS images (
    image_id TEXT PRIMARY KEY,
    downloaded BOOLEAN
)
''')

# Загрузка HAR файла
try:
    with open('x2.com.har', 'r', encoding='utf-8') as f:
        har_parser = HarParser(json.loads(f.read()))
except Exception as e:
    logging.error(f"Failed to read HAR file: {e}")
    raise

data = har_parser.har_data["entries"]
image_urls = []

# Обрабатываем все ссылки из HAR файла
for entry in data:
    if entry["response"]["content"]["mimeType"].startswith("image/"):
        image_urls.append(entry["request"]["url"])

# Загрузка и сохранение картинок
for link in image_urls:
    if 'media' in link:
        # Извлечение идентификатора из URL
        match = re.search(PATTERN, link)
        if match:
            image_id = match.group(1)
            new_link = f"https://pbs.twimg.com/media/{image_id}?format=jpg&name=4096x4096"

            # Проверка, есть ли идентификатор в базе данных и загружена ли картинка
            cursor.execute('SELECT downloaded FROM images WHERE image_id = ?', (image_id,))
            result = cursor.fetchone()

            # Проверка на наличие и статус загрузки
            if result is None or not bool(result[0]):
                try:
                    # Скачиваем картинку
                    response = requests.get(new_link)
                    if response.status_code == 200:
                        # Формируем путь к файлу в папке media
                        image_name = f"{image_id}.jpg"
                        image_path = os.path.join(MEDIA_DIR, image_name)

                        # Сохраняем картинку в файл
                        with open(image_path, 'wb') as img_file:
                            img_file.write(response.content)

                        # Обновляем базу данных
                        cursor.execute('''
                        INSERT OR REPLACE INTO images (image_id, downloaded) 
                        VALUES (?, ?)
                        ''', (image_id, True))

                        logging.info(f"Downloaded and saved: {new_link} as {image_path}")

                        # Сохранение изменений в базе данных
                        conn.commit()

                    else:
                        logging.error(f"Failed to download: {new_link} (Status code: {response.status_code})")
                except Exception as e:
                    logging.error(f"Exception occurred while downloading {new_link}: {e}")

                # Задержка между загрузками
                time.sleep(5)
            else:
                logging.info(f"Already downloaded: {new_link}")
        else:
            logging.error(f"Failed to extract image ID from: {link}")

# Закрытие соединения с базой данных
conn.close()
