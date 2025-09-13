import logging
from database import db_connection

logger = logging.getLogger(__name__)

async def check_admin_rights(user_id):
    """Проверка прав администратора"""
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT role FROM admins WHERE telegram_id = ? AND role = 'admin'", (user_id,))
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        return False

async def get_user_role(user_id):
    """Получить роль пользователя"""
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            
            # Проверяем админа
            cur.execute("SELECT role FROM admins WHERE telegram_id = ?", (user_id,))
            admin = cur.fetchone()
            if admin:
                return admin['role']
            
            # Проверяем студента
            cur.execute("SELECT id FROM students WHERE telegram_id = ?", (user_id,))
            student = cur.fetchone()
            return 'student' if student else 'guest'
            
    except Exception as e:
        logger.error(f"Ошибка получения роли: {e}")
        return 'guest'

def create_fake_update(query):
    """Создать fake update объект для обработки callback_query"""
    class FakeUpdate:
        def __init__(self, query):
            self.callback_query = query
    
    return FakeUpdate(query)