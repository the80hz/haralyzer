# scraper.py
import asyncio
from playwright.async_api import async_playwright
import re
import aiosqlite
from db import init_db, DATABASE

TARGET_URL = 'https://x.com/'

# Глобальные счетчики
total_found = 0
total_saved = 0

async def extract_post_data(post, db):
    global total_found, total_saved
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

        # Увеличиваем счетчик найденных постов
        total_found += 1

        # Проверка наличия поста в базе данных
        async with db.execute('SELECT id FROM posts WHERE id = ?', (post_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                # Пост уже существует
                return

        # Извлечение имени пользователя
        username_container = await post.query_selector('[data-testid="User-Name"]')
        username = ''
        if username_container:
            username_link = await username_container.query_selector('a[href^="/"]')
            if username_link:
                username_href = await username_link.get_attribute('href')
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
                url_match = re.search(r'(https:\/\/pbs\.twimg\.com\/media\/[^?]+\?format=jpg)', src)
                if url_match:
                    base_url = url_match.group(1)
                    high_res_url = base_url + '&name=4096x4096'
                    images.append(high_res_url)

        if not images:
            # Если в посте нет изображений, пропускаем его
            return

        # Вставка данных в базу данных
        await db.execute('INSERT INTO posts (id, username, datetime) VALUES (?, ?, ?)',
                         (post_id, username, datetime))
        for index, image_url in enumerate(images, start=1):
            await db.execute('INSERT INTO images (post_id, image_number, image_url) VALUES (?, ?, ?)',
                             (post_id, index, image_url))
        await db.commit()
        total_saved += 1
        print(f'✅ Сохранён пост {post_id}')
        print(f'   Автор: {username}')
        print(f'   Дата: {datetime}')
        print(f'   Количество изображений: {len(images)}')
        print(f'   Всего найдено: {total_found}, сохранено: {total_saved}\n')

    except Exception as e:
        print(f'⚠️ Ошибка при извлечении данных поста: {e}')

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
            print('🚀 Скрипт запущен. Пожалуйста, начните скроллить страницу.')

            async def periodic_scan():
                while True:
                    await asyncio.sleep(1)
                    await scan_posts(page, db)
                    print(f'📊 Статистика: Всего найдено: {total_found}, сохранено: {total_saved}\n')

            # Запуск периодического сканирования в фоновом режиме
            scan_task = asyncio.create_task(periodic_scan())

            # Закрытие браузера после 1 часа (опционально)
            async def close_after_timeout():
                await asyncio.sleep(3600)  # 1 час
                scan_task.cancel()
                await browser.close()
                await db.close()
                print('🔚 Скрипт завершен.')

            timeout_task = asyncio.create_task(close_after_timeout())

            try:
                await asyncio.gather(scan_task, timeout_task)
            except asyncio.CancelledError:
                pass

if __name__ == '__main__':
    asyncio.run(main())
