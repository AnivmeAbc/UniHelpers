from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging
from database import db_connection
from keyboards import get_student_keyboard, get_admin_keyboard
from utils import get_user_role, create_fake_update

logger = logging.getLogger(__name__)

class BaseHandlers:
    """Базовые обработчики команд"""
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name
        
        try:
            role = await get_user_role(user_id)
            
            if role in ['admin', 'headman']:
                welcome_text = f"👋 Добро пожаловать, {user_name}!\nВаша роль: {role}\n\nВыберите действие:"
                keyboard = get_admin_keyboard(role)
                
            elif role == 'student':
                with db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT full_name FROM students WHERE telegram_id = ?", (user_id,))
                    result = cur.fetchone()
                
                if result:
                    full_name = result['full_name']
                    welcome_text = f"👋 Привет, {full_name}!\nЯ твой учебный помощник.\n\nВыберите действие:"
                    keyboard = get_student_keyboard()
                else:
                    welcome_text = f"👋 Привет, {user_name}!\n\nВы не зарегистрированы в системе. Хотите зарегистрироваться?"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Зарегистрироваться", callback_data='register_student')],
                        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
                    ])
                
            else:
                welcome_text = f"👋 Привет, {user_name}!\n\nВы не зарегистрированы в системе. Хотите зарегистрироваться?"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Зарегистрироваться", callback_data='register_student')],
                    [InlineKeyboardButton("❓ Помощь", callback_data='help')]
                ])
            
            await update.message.reply_text(welcome_text, reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"Ошибка в команде start: {e}")
            await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 UniHelperBot - Помощник для студентов

Основные команды:
/start - Начать работу с ботом
/help - Показать эту справку
/cancel - Отменить текущую операцию

Используйте кнопки меню для доступа к функциям.
        """
        await update.message.reply_text(help_text)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /cancel"""
        await update.message.reply_text("Операция отменена.")
        return ConversationHandler.END
    
    async def back_to_main_menu(self, query):
        """Вернуться в главное меню"""
        user_id = query.from_user.id
        
        try:
            role = await get_user_role(user_id)
            
            if role in ['admin', 'headman']:
                keyboard = get_admin_keyboard(role)
                await query.edit_message_text("👨‍💼 Главное меню\n\nВыберите действие:", reply_markup=keyboard)
                
            elif role == 'student':
                keyboard = get_student_keyboard()
                await query.edit_message_text("👋 Главное меню\n\nВыберите действие:", reply_markup=keyboard)
                
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Зарегистрироваться", callback_data='register_student')],
                    [InlineKeyboardButton("❓ Помощь", callback_data='help')]
                ])
                await query.edit_message_text("👋 Главное меню\n\nВы не зарегистрированы в системе:", reply_markup=keyboard)
                        
        except Exception as e:
            logger.error(f"Ошибка при возврате в главное меню: {e}")
            await query.edit_message_text("⚠️ Произошла ошибка. Попробуйте позже.")
    
    async def back_to_management(self, query):
        """Вернуться в меню управления студентами"""
        from .admin import AdminHandlers
        admin_handlers = AdminHandlers()
        fake_update = create_fake_update(query)
        await admin_handlers.start_student_management(fake_update, {})
    
    async def back_to_groups_management(self, query):
        """Вернуться в меню управления группами"""
        from .group import GroupHandlers
        group_handlers = GroupHandlers()
        fake_update = create_fake_update(query)
        await group_handlers.start_group_management(fake_update, {})
    
    async def back_to_subjects_management(self, query):
        """Вернуться в меню управления предметами"""
        from .subject import SubjectHandlers
        subject_handlers = SubjectHandlers()
        fake_update = create_fake_update(query)
        await subject_handlers.start_subject_management(fake_update, {})