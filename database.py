import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@contextmanager
def db_connection():
    """Контекстный менеджер для соединения с БД"""
    conn = sqlite3.connect('university_bot.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise e
    finally:
        conn.close()

def init_database():
    """Инициализация базы данных"""
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            
            # Таблица администраторов
            cur.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE,
                    role TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица групп
            cur.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица студентов
            cur.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    group_id INTEGER,
                    telegram_id INTEGER UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES groups (id)
                )
            ''')
            
            # Таблица предметов
            cur.execute('''
                CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица связи групп и предметов
            cur.execute('''
                CREATE TABLE IF NOT EXISTS group_subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    subject_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES groups (id),
                    FOREIGN KEY (subject_id) REFERENCES subjects (id),
                    UNIQUE(group_id, subject_id)
                )
            ''')
            
            # Таблица занятий
            cur.execute('''
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_subject_id INTEGER,
                    date DATE NOT NULL,
                    topic TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_subject_id) REFERENCES group_subjects (id)
                )
            ''')
            
            # Таблица посещаемости
            cur.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    lesson_id INTEGER,
                    status TEXT NOT NULL CHECK(status IN ('present', 'absent', 'late')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students (id),
                    FOREIGN KEY (lesson_id) REFERENCES lessons (id),
                    UNIQUE(student_id, lesson_id)
                )
            ''')
            
            conn.commit()
            logger.info("База данных успешно инициализирована")
            
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise