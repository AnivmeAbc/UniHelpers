from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
import logging
from database import db_connection
from config import MANAGE_GROUPS, ADD_GROUP_NAME, EDIT_GROUP_SELECT, EDIT_GROUP_NAME, DELETE_GROUP
from utils import check_admin_rights
from keyboards import get_back_button, get_main_menu_button

logger = logging.getLogger(__name__)

class GroupHandlers:
    """Обработчики для управления группами"""
    
    async def start_group_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
        """Начало управления группами"""
        if query is None:
            query = update.callback_query
            await query.answer()
        
        if not await check_admin_rights(query.from_user.id):
            await query.edit_message_text("❌ Доступно только администраторам")
            return ConversationHandler.END
        
        keyboard = [
            [InlineKeyboardButton("📚 Список групп", callback_data='list_groups')],
            [InlineKeyboardButton("➕ Добавить группу", callback_data='add_group')],
            [InlineKeyboardButton("✏️ Редактировать группу", callback_data='edit_group')],
            [InlineKeyboardButton("🗑️ Удалить группу", callback_data='delete_group')],
            get_back_button('main')[0]
        ]
        
        await query.edit_message_text(
            "📚 Управление группами\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MANAGE_GROUPS

    async def manage_groups_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка действий управления группами"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == 'list_groups':
            await self.list_groups(query)
            return MANAGE_GROUPS
            
        elif data == 'add_group':
            await query.edit_message_text("Введите название новой группы:")
            return ADD_GROUP_NAME
            
        elif data == 'edit_group':
            await self.show_groups_for_edit(query)
            return EDIT_GROUP_SELECT
            
        elif data == 'delete_group':
            await self.show_groups_for_delete(query)
            return DELETE_GROUP
            
        elif data == 'back_to_main':
            from .base import BaseHandlers
            base_handlers = BaseHandlers()
            await base_handlers.back_to_main_menu(query)
            return ConversationHandler.END
            
        return MANAGE_GROUPS

    async def add_group_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление новой группы"""
        group_name = update.message.text.strip()
        
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                
                # Проверяем, нет ли уже группы с таким названием
                cur.execute("SELECT id FROM groups WHERE name = ?", (group_name,))
                if cur.fetchone():
                    await update.message.reply_text("❌ Группа с таким названием уже существует!")
                    return ConversationHandler.END
                
                # Добавляем группу
                cur.execute("INSERT INTO groups (name) VALUES (?)", (group_name,))
                conn.commit()
            
            keyboard = [
                [InlineKeyboardButton("🔙 К управлению группами", callback_data='back_to_groups_management')],
                get_main_menu_button()
            ]
            
            await update.message.reply_text(
                f"✅ Группа '{group_name}' успешно добавлена!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении группы: {e}")
            await update.message.reply_text("❌ Ошибка при добавлении группы")
        
        return ConversationHandler.END

    async def show_groups_for_edit(self, query):
        """Показать список групп для редактирования"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM groups ORDER BY name")
                groups = cur.fetchall()
                
                if groups:
                    keyboard = []
                    for group in groups:
                        keyboard.append([InlineKeyboardButton(group['name'], callback_data=f'edit_group_{group["id"]}')])
                    
                    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_groups_management')])
                    
                    await query.edit_message_text(
                        "✏️ Выберите группу для редактирования:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.edit_message_text("📝 Группы не найдены")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении групп: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")

    async def edit_group_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора группы для редактирования"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_groups_management':
            await self.start_group_management(update, context, query)
            return MANAGE_GROUPS
        
        if query.data.startswith('edit_group_'):
            group_id = int(query.data.split('_')[2])
            context.user_data['edit_group_id'] = group_id
            
            # Получаем текущее название группы
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                
                keyboard = [get_back_button('groups_management')]
                
                await query.edit_message_text(
                    f"✏️ Редактирование группы:\n\n"
                    f"Текущее название: {group_name}\n\n"
                    f"Введите новое название группы:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return EDIT_GROUP_NAME
                    
            except Exception as e:
                logger.error(f"Ошибка при получении данных группы: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке данных")
        
        return MANAGE_GROUPS

    async def edit_group_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Изменение названия группы"""
        new_group_name = update.message.text.strip()
        group_id = context.user_data['edit_group_id']
        
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                
                # Проверяем, нет ли уже группы с таким названием
                cur.execute("SELECT id FROM groups WHERE name = ? AND id != ?", (new_group_name, group_id))
                if cur.fetchone():
                    await update.message.reply_text("❌ Группа с таким названием уже существует!")
                    return ConversationHandler.END
                
                # Обновляем название группы
                cur.execute("UPDATE groups SET name = ? WHERE id = ?", (new_group_name, group_id))
                conn.commit()
            
            keyboard = [
                [InlineKeyboardButton("🔙 К управлению группами", callback_data='back_to_groups_management')],
                get_main_menu_button()
            ]
            
            await update.message.reply_text(
                f"✅ Название группы успешно изменено на '{new_group_name}'!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
                
        except Exception as e:
            logger.error(f"Ошибка при изменении группы: {e}")
            await update.message.reply_text("❌ Ошибка при изменении группы")
        
        return ConversationHandler.END

    async def show_groups_for_delete(self, query):
        """Показать список групп для удаления"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM groups ORDER BY name")
                groups = cur.fetchall()
                
                if groups:
                    keyboard = []
                    for group in groups:
                        # Проверяем, есть ли студенты в группе
                        cur.execute("SELECT COUNT(*) FROM students WHERE group_id = ?", (group['id'],))
                        student_count = cur.fetchone()[0]
                        
                        btn_text = f"{group['name']} ({student_count} студентов)"
                        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'delete_group_{group["id"]}')])
                    
                    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_groups_management')])
                    
                    await query.edit_message_text(
                        "🗑️ Выберите группу для удаления:\n(в скобках указано количество студентов)",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.edit_message_text("📝 Группы не найдены")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении групп: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")

    async def delete_group_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение удаления группы"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_groups_management':
            await self.start_group_management(update, context, query)
            return MANAGE_GROUPS
        
        if query.data.startswith('delete_group_'):
            group_id = int(query.data.split('_')[2])
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Получаем данные группы
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                    
                    # Проверяем, есть ли студенты в группе
                    cur.execute("SELECT COUNT(*) FROM students WHERE group_id = ?", (group_id,))
                    student_count = cur.fetchone()[0]
                    
                    if student_count > 0:
                        keyboard = [
                            [InlineKeyboardButton("✅ Удалить вместе со студентами", callback_data=f'confirm_delete_group_with_students_{group_id}')],
                            [InlineKeyboardButton("🔁 Переместить студентов в другую группу", callback_data=f'move_students_{group_id}')],
                            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_delete_group')]
                        ]
                        
                        await query.edit_message_text(
                            f"⚠️ В группе '{group_name}' есть {student_count} студент(ов)!\n\n"
                            f"Что вы хотите сделать?",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        keyboard = [
                            [InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_group_{group_id}')],
                            [InlineKeyboardButton("❌ Нет, отмена", callback_data='cancel_delete_group')]
                        ]
                        
                        await query.edit_message_text(
                            f"⚠️ Вы уверены, что хотите удалить группу '{group_name}'?",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    
                    return DELETE_GROUP
                    
            except Exception as e:
                logger.error(f"Ошибка при получении данных группы: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке данных")
        
        elif query.data.startswith('confirm_delete_group_'):
            group_id = int(query.data.split('_')[3])
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                    
                    cur.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                    conn.commit()
                
                keyboard = [
                    [InlineKeyboardButton("🔙 К управлению группами", callback_data='back_to_groups_management')],
                    get_main_menu_button()
                ]
                
                await query.edit_message_text(
                    f"✅ Группа '{group_name}' удалена!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                    
            except Exception as e:
                logger.error(f"Ошибка при удалении группы: {e}")
                await query.edit_message_text("❌ Ошибка при удалении группы")
        
        elif query.data == 'cancel_delete_group':
            await self.start_group_management(update, context, query)
            return MANAGE_GROUPS
        
        return ConversationHandler.END

    async def list_groups(self, query):
        """Показать список всех групп"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT g.id, g.name, COUNT(s.id) as student_count
                    FROM groups g
                    LEFT JOIN students s ON g.id = s.group_id
                    GROUP BY g.id
                    ORDER BY g.name
                """)
                
                groups = cur.fetchall()
                
                if groups:
                    text = "📚 Список всех групп:\n\n"
                    for group in groups:
                        text += f"• {group['name']} - {group['student_count']} студент(ов)\n"
                    
                    text += f"\nВсего групп: {len(groups)}"
                else:
                    text = "📝 Группы не найдены"
                
                keyboard = [
                    get_back_button('groups_management')[0],
                    get_main_menu_button()
                ]
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                
        except Exception as e:
            logger.error(f"Ошибка при получении списка групп: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")