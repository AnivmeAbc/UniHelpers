from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
import logging
from database import db_connection
from config import MANAGE_STUDENTS, ADD_STUDENT_NAME, ADD_STUDENT_GROUP, EDIT_STUDENT_SELECT, DELETE_STUDENT
from utils import check_admin_rights
from keyboards import get_groups_keyboard, get_back_button, get_main_menu_button

logger = logging.getLogger(__name__)

class AdminHandlers:
    """Обработчики для администраторов"""
    
    async def start_student_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
        """Начало управления студентами"""
        if query is None:
            query = update.callback_query
            await query.answer()
        
        if not await check_admin_rights(query.from_user.id):
            await query.edit_message_text("❌ Доступно только администраторам")
            return ConversationHandler.END
        
        keyboard = [
            [InlineKeyboardButton("👥 Список студентов", callback_data='list_students')],
            [InlineKeyboardButton("➕ Добавить студента", callback_data='add_student')],
            [InlineKeyboardButton("✏️ Редактировать студента", callback_data='edit_student')],
            [InlineKeyboardButton("🗑️ Удалить студента", callback_data='delete_student')],
            get_back_button('main')[0]
        ]
        
        await query.edit_message_text(
            "👥 Управление студентами\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MANAGE_STUDENTS
    
    async def manage_students_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка действий управления студентами"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == 'list_students':
            await self.list_students(query)
            return MANAGE_STUDENTS
            
        elif data == 'add_student':
            await query.edit_message_text("Введите ФИО нового студента:")
            return ADD_STUDENT_NAME
            
        elif data == 'edit_student':
            await self.show_students_for_edit(query)
            return EDIT_STUDENT_SELECT
            
        elif data == 'delete_student':
            await self.show_students_for_delete(query)
            return DELETE_STUDENT
            
        elif data == 'back_to_main':
            from .base import BaseHandlers
            base_handlers = BaseHandlers()
            await base_handlers.back_to_main_menu(query)
            return ConversationHandler.END
            
        return MANAGE_STUDENTS

    async def add_student_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение имени нового студента"""
        context.user_data['new_student'] = {'name': update.message.text}
        
        try:
            keyboard = get_groups_keyboard()
            keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data='cancel_add')])
            
            await update.message.reply_text(
                f"Выберите группу для студента {update.message.text}:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ADD_STUDENT_GROUP
                
        except Exception as e:
            logger.error(f"Ошибка при получении групп: {e}")
            await update.message.reply_text("❌ Ошибка при загрузке групп")
            return ConversationHandler.END
    
    async def add_student_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление студента с выбранной группой"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel_add':
            await self.start_student_management(update, context, query)
            return MANAGE_STUDENTS
        
        if query.data.startswith('group_'):
            group_id = int(query.data.split('_')[1])
            student_name = context.user_data['new_student']['name']
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO students (full_name, group_id) VALUES (?, ?)",
                        (student_name, group_id)
                    )
                    conn.commit()
                    
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                
                keyboard = [
                    [InlineKeyboardButton("🔙 К управлению студентами", callback_data='back_to_management')],
                    get_main_menu_button()
                ]
                
                await query.edit_message_text(
                    f"✅ Студент {student_name} добавлен в группу {group_name}!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                    
            except Exception as e:
                logger.error(f"Ошибка при добавлении студента: {e}")
                await query.edit_message_text("❌ Ошибка при добавлении студента")
        
        return ConversationHandler.END

    async def show_students_for_edit(self, query):
        """Показать список студентов для редактирования"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT s.id, s.full_name, g.name 
                    FROM students s 
                    JOIN groups g ON s.group_id = g.id 
                    ORDER BY g.name, s.full_name
                """)
                students = cur.fetchall()
                
                if students:
                    keyboard = []
                    for student in students:
                        btn_text = f"{student['full_name']} ({student['name']})"
                        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'edit_{student["id"]}')])
                    
                    keyboard.append(get_back_button('management'))
                    
                    await query.edit_message_text(
                        "✏️ Выберите студента для редактирования:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.edit_message_text("📝 Студенты не найдены")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении студентов: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")

    async def edit_student_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора студента для редактирования"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_management':
            await self.start_student_management(update, context, query)
            return MANAGE_STUDENTS
        
        if query.data.startswith('edit_'):
            student_id = int(query.data.split('_')[1])
            keyboard = [get_back_button('management')]
            await query.edit_message_text(
                f"✏️ Редактирование студента ID: {student_id}\n\nФункция в разработке",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return MANAGE_STUDENTS
        
        return MANAGE_STUDENTS

    async def show_students_for_delete(self, query):
        """Показать список студентов для удаления"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT s.id, s.full_name, g.name 
                    FROM students s 
                    JOIN groups g ON s.group_id = g.id 
                    ORDER BY g.name, s.full_name
                """)
                students = cur.fetchall()
                
                if students:
                    keyboard = []
                    for student in students:
                        btn_text = f"{student['full_name']} ({student['name']})"
                        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'delete_{student["id"]}')])
                    
                    keyboard.append(get_back_button('management'))
                    
                    await query.edit_message_text(
                        "🗑️ Выберите студента для удаления:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.edit_message_text("📝 Студенты не найдены")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении студентов: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")

    async def delete_student_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение удаления студента"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_management':
            await self.start_student_management(update, context, query)
            return MANAGE_STUDENTS
        
        if query.data.startswith('delete_'):
            student_id = int(query.data.split('_')[1])
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT full_name FROM students WHERE id = ?", (student_id,))
                    student_name = cur.fetchone()['name']
                    
                    keyboard = [
                        [InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_{student_id}')],
                        [InlineKeyboardButton("❌ Нет, отмена", callback_data='cancel_delete')]
                    ]
                    
                    await query.edit_message_text(
                        f"⚠️ Вы уверены, что хотите удалить студента {student_name}?",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return DELETE_STUDENT
                    
            except Exception as e:
                logger.error(f"Ошибка при получении данных студента: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке данных")
        
        elif query.data.startswith('confirm_delete_'):
            student_id = int(query.data.split('_')[2])
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT full_name FROM students WHERE id = ?", (student_id,))
                    student_name = cur.fetchone()['name']
                    cur.execute("DELETE FROM students WHERE id = ?", (student_id,))
                    conn.commit()
                
                keyboard = [
                    [InlineKeyboardButton("🔙 К управлению студентами", callback_data='back_to_management')],
                    get_main_menu_button()
                ]
                
                await query.edit_message_text(
                    f"✅ Студент {student_name} удален!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                    
            except Exception as e:
                logger.error(f"Ошибка при удалении студента: {e}")
                await query.edit_message_text("❌ Ошибка при удалении студента")
        
        elif query.data == 'cancel_delete':
            await self.start_student_management(update, context, query)
            return MANAGE_STUDENTS
        
        return ConversationHandler.END

    async def list_students(self, query):
        """Показать список всех студентов"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT s.id, s.full_name, g.name, s.telegram_id 
                    FROM students s 
                    JOIN groups g ON s.group_id = g.id 
                    ORDER BY g.name, s.full_name
                """)
                students = cur.fetchall()
                
                if students:
                    text = "👥 Список всех студентов:\n\n"
                    current_group = None
                    
                    for student in students:
                        if student['name'] != current_group:
                            text += f"\n📚 Группа: {student['name']}\n"
                            current_group = student['name']
                        
                        status = "✅ В боте" if student['telegram_id'] else "❌ Не в боте"
                        text += f"• {student['full_name']} ({status})\n"
                    
                    text += f"\nВсего студентов: {len(students)}"
                else:
                    text = "📝 Студенты не найдены"
                
                keyboard = [
                    get_back_button('management')[0],
                    get_main_menu_button()
                ]
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                
        except Exception as e:
            logger.error(f"Ошибка при получении списка студентов: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")