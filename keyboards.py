from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import db_connection

def get_student_keyboard():
    """Клавиатура для студента"""
    keyboard = [
        [InlineKeyboardButton("📊 Моя посещаемость", callback_data='my_attendance')],
        [InlineKeyboardButton("📚 Полезные материалы", callback_data='materials')],
        [InlineKeyboardButton("📅 Мое расписание", callback_data='schedule')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard(role):
    """Клавиатура для админа"""
    keyboard = [
        [InlineKeyboardButton("✅ Отметить посещаемость", callback_data='start_attendance')],
        [InlineKeyboardButton("📊 Отчет по посещаемости", callback_data='generate_report')],
        [InlineKeyboardButton("👥 Управление студентами", callback_data='manage_students')],
        [InlineKeyboardButton("📚 Управление предметами", callback_data='manage_subjects')],
        [InlineKeyboardButton("📚 Управление группами", callback_data='manage_groups')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_main')]
    ]
    
    if role == 'admin':
        keyboard.insert(4, [InlineKeyboardButton("💬 Управление чатами", callback_data='manage_chats')])
    
    return InlineKeyboardMarkup(keyboard)

def get_groups_keyboard(prefix='group'):
    """Клавиатура со списком групп"""
    keyboard = []
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM groups ORDER BY name")
            groups = cur.fetchall()
            
            for group in groups:
                keyboard.append([InlineKeyboardButton(group['name'], callback_data=f'{prefix}_{group["id"]}')])
                
    except Exception as e:
        print(f"Ошибка получения групп: {e}")
    
    return keyboard

def get_back_button(target='main'):
    """Кнопка назад"""
    callback_data = f'back_to_{target}'
    return [InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]

def get_main_menu_button():
    """Кнопка главного меню"""
    return [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_main')]