import aiosqlite
from config import config

async def init_db():
    async with aiosqlite.connect(config.DB_PATH) as db:
        # Dropping table for dev purposes since schema changed drastically
        # In prod you would use migration
        # await db.execute('DROP TABLE IF EXISTS users') 
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                email TEXT,
                age INTEGER,
                is_aiesec_member BOOLEAN,
                source TEXT,
                source_details TEXT,
                education_status TEXT,
                university TEXT,
                course TEXT,
                specialty TEXT,
                work_status BOOLEAN,
                work_sphere TEXT,
                missing_skills TEXT,
                expectations TEXT,
                registration_date TEXT,
                is_ambassador_candidate BOOLEAN DEFAULT 0
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        await db.execute('''
            INSERT OR IGNORE INTO bot_settings (key, value)
            VALUES ('registration_form_mode', 'full')
        ''')
        await db.commit()

async def add_user(data: dict):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO users (
                telegram_id, username, full_name, email, age,
                is_aiesec_member, source, source_details,
                education_status, university, course, specialty,
                work_status, work_sphere,
                missing_skills, expectations, registration_date,
                is_ambassador_candidate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['telegram_id'],
            data.get('username'),
            data.get('full_name', ''),
            data.get('email', '-'),
            data.get('age'),
            data.get('is_aiesec_member', False),
            data.get('source', '-'),
            data.get('source_details'),
            data.get('education_status', '-'),
            data.get('university'),
            data.get('course'),
            data.get('specialty'),
            data.get('work_status', False),
            data.get('work_sphere'),
            data.get('missing_skills', '-'),
            data.get('expectations', '-'),
            data['registration_date'],
            data.get('is_ambassador_candidate', False)
        ))
        await db.commit()

async def get_registration_form_mode() -> str:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM bot_settings WHERE key = 'registration_form_mode'"
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return "full"
            mode = (row[0] or "full").strip().lower()
            return mode if mode in {"full", "short"} else "full"

async def set_registration_form_mode(mode: str):
    normalized_mode = (mode or "full").strip().lower()
    if normalized_mode not in {"full", "short"}:
        raise ValueError("Invalid registration form mode")

    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO bot_settings (key, value)
            VALUES ('registration_form_mode', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (normalized_mode,)
        )
        await db.commit()

async def get_user(telegram_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_user_by_username(username: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Ensure username starts with @ for search, or try both
        if not username.startswith('@'):
            username = f"@{username}"
            
        async with db.execute('SELECT * FROM users WHERE username = ? COLLATE NOCASE', (username,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def set_ambassador_candidate(telegram_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('UPDATE users SET is_ambassador_candidate = 1 WHERE telegram_id = ?', (telegram_id,))
        await db.commit()

async def get_all_users_ids():
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute('SELECT telegram_id FROM users') as cursor:
            return [row[0] for row in await cursor.fetchall()]

async def get_stats():
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            total = (await cursor.fetchone())[0]
        
        async with db.execute('SELECT COUNT(*) FROM users WHERE is_ambassador_candidate = 1') as cursor:
            ambassadors = (await cursor.fetchone())[0]

        async with db.execute('''
            SELECT university, COUNT(*) as cnt 
            FROM users 
            GROUP BY university 
            ORDER BY cnt DESC 
            LIMIT 3
        ''') as cursor:
            top_universities = await cursor.fetchall()

    return total, ambassadors, top_universities

async def export_users_csv():
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute('SELECT * FROM users') as cursor:
             # Get headers
            headers = [description[0] for description in cursor.description]
            rows = await cursor.fetchall()
            return headers, rows
