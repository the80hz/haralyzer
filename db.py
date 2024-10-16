# db.py
import aiosqlite

DATABASE = 'posts.db'

async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                username TEXT,
                datetime TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT,
                image_number INTEGER,
                image_url TEXT,
                FOREIGN KEY(post_id) REFERENCES posts(id)
            )
        ''')
        await db.commit()
