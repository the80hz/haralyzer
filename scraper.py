# scraper.py
import asyncio
from playwright.async_api import async_playwright
import re
import aiosqlite
from db import init_db, DATABASE

TARGET_URL = 'https://x.com/'  # Замените на реальный URL

async def extract_post_data(post, db):
    try:
        # Извлечение ID поста из ссылки
        post_link = await post.query_selector('a[href*="/status/"]')
        if not post_link:
            return

        href = await post_link.get_attribute('href')
        post_id_match = re.search(r'/status/(\d+)', href)
        if not post_id_match:
            return
        post_id = post_id_match.group(1)

        # Проверка наличия поста в базе данных
        async with db.execute('SELECT id FROM posts WHERE id = ?', (post_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                # Пост уже существует
                return

        # Извлечение имени пользователя
        # Предполагаем, что ссылка на пользователя находится в ближайшем родительском элементе
        username_element = await post.query_selector('a[href*="/"]')
        username = ''
        if username_element:
            username_href = await username_element.get_attribute('href')
            if username_href:
                username = username_href.strip('/').split('/')[0]

        # Извлечение даты
        time_element = await post.query_selector('time')
        datetime = ''
        if time_element:
            datetime = await time_element.get_attribute('datetime')

        # Извлечение ссылок на изображения
        image_elements = await post.query_selector_all('[data-testid="tweetPhoto"] img')
        images = []
        for img in image_elements:
            src = await img.get_attribute('src')
            if src:
                # Извлечение части URL для изменения
                url_match = re.search(r'(https:/\/pbs\.twimg\.com\/media\/[^?]+\?format=jpg)', src)
                if url_match:
                    base_url = url_match.group(1)
                    high_res_url = base_url + '&name=4096x4096'
                    images.append(high_res_url)

        # Вставка данных в базу данных
        await db.execute('INSERT INTO posts (id, username, datetime) VALUES (?, ?, ?)',
                         (post_id, username, datetime))
        for index, image_url in enumerate(images, start=1):
            await db.execute('INSERT INTO images (post_id, image_number, image_url) VALUES (?, ?, ?)',
                             (post_id, index, image_url))
        await db.commit()
        print(f'Сохранен пост {post_id} от {username}')

    except Exception as e:
        print(f'Ошибка при извлечении данных поста: {e}')

async def scan_posts(page, db):
    # Селектор поста, возможно потребуется корректировка
    posts = await page.query_selector_all('[data-testid="tweet"]')
    for post in posts:
        await extract_post_data(post, db)

async def main():
    await init_db()
    async with aiosqlite.connect(DATABASE) as db:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # headless=True для безголового режима
            page = await browser.new_page()
            await page.goto(TARGET_URL, wait_until='networkidle')

            # Первоначальное сканирование
            await scan_posts(page, db)

            # Настройка отслеживания новых постов при скроллинге
            # Поскольку пользователь будет скроллить вручную, будем периодически сканировать страницу на новые посты
            print('Скрипт запущен. Пожалуйста, начните скроллить страницу.')

            async def periodic_scan():
                while True:
                    await asyncio.sleep(5)  # Каждые 5 секунд
                    await scan_posts(page, db)

            # Запуск периодического сканирования в фоновом режиме
            scan_task = asyncio.create_task(periodic_scan())

            # Закрытие браузера после 1 часа (опционально)
            async def close_after_timeout():
                await asyncio.sleep(3600)  # 1 час
                scan_task.cancel()
                await browser.close()
                await db.close()
                print('Скрипт завершен.')

            timeout_task = asyncio.create_task(close_after_timeout())

            try:
                await asyncio.gather(scan_task, timeout_task)
            except asyncio.CancelledError:
                pass

if __name__ == '__main__':
    asyncio.run(main())
