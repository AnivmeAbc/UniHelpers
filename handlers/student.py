from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
import logging
from database import db_connection
from config import REGISTER_NAME, REGISTER_GROUP
from keyboards import get_groups_keyboard, get_back_button, get_main_menu_button

logger = logging.getLogger(__name__)

class StudentHandlers:
    """Обработчики для студентов"""
    
    async def start_student_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало регистрации студента"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Проверяем, не зарегистрирован ли уже студент
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM students WHERE telegram_id = ?", (user_id,))
                if cur.fetchone():
                    await query.edit_message_text("✅ Вы уже зарегистрированы в системе!")
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Ошибка при проверке регистрации: {e}")
        
        await query.edit_message_text("👋 Давайте зарегистрируем вас в системе!\n\nВведите ваше ФИО:")
        return REGISTER_NAME

    async def register_student_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка введенного имени при регистрации"""
        context.user_data['register_student'] = {'name': update.message.text}
        
        # Получаем список групп для выбора
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM groups ORDER BY name")
                groups = cur.fetchall()
                
                if not groups:
                    await update.message.reply_text("❌ В системе нет групп. Обратитесь к администратору.")
                    return ConversationHandler.END
            
            keyboard = get_groups_keyboard('register_group')
            keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data='cancel_register')])
            keyboard.append(get_main_menu_button())
            
            await update.message.reply_text(
                "Выберите вашу группу:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return REGISTER_GROUP
                
        except Exception as e:
            logger.error(f"Ошибка при получении групп: {e}")
            await update.message.reply_text("❌ Ошибка при загрузке групп")
            return ConversationHandler.END

    async def register_student_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершение регистрации студента"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel_register':
            await query.edit_message_text("❌ Регистрация отменена")
            return ConversationHandler.END
        
        if query.data.startswith('register_group_'):
            group_id = int(query.data.split('_')[2])
            student_name = context.user_data['register_student']['name']
            user_id = query.from_user.id
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Проверяем, нет ли уже студента с таким Telegram ID
                    cur.execute("SELECT id FROM students WHERE telegram_id = ?", (user_id,))
                    if cur.fetchone():
                        await query.edit_message_text("❌ Вы уже зарегистрированы в системе!")
                        return ConversationHandler.END
                    
                    # Добавляем студента
                    cur.execute(
                        "INSERT INTO students (full_name, group_id, telegram_id) VALUES (?, ?, ?)",
                        (student_name, group_id, user_id)
                    )
                    conn.commit()
                    
                    # Получаем название группы для сообщения
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                
                keyboard = [get_main_menu_button()]
                
                await query.edit_message_text(
                    f"✅ Регистрация завершена!\n\n"
                    f"ФИО: {student_name}\n"
                    f"Группа: {group_name}\n\n"
                    f"Теперь вам доступны все функции бота!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                    
            except Exception as e:
                logger.error(f"Ошибка при регистрации студента: {e}")
                await query.edit_message_text("❌ Ошибка при регистрации. Обратитесь к администратору.")
        
        return ConversationHandler.END