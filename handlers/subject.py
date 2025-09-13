from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
import logging
from database import db_connection
from config import MANAGE_SUBJECTS, ADD_SUBJECT_NAME, SELECT_GROUP_FOR_SUBJECT, DELETE_SUBJECT
from utils import check_admin_rights
from keyboards import get_groups_keyboard, get_back_button, get_main_menu_button

logger = logging.getLogger(__name__)

class SubjectHandlers:
    """Обработчики для управления предметами"""
    
    async def start_subject_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
        """Начало управления предметами"""
        if query is None:
            query = update.callback_query
            await query.answer()
        
        if not await check_admin_rights(query.from_user.id):
            await query.edit_message_text("❌ Доступно только администраторам")
            return ConversationHandler.END
        
        keyboard = [
            [InlineKeyboardButton("📚 Список предметов по группам", callback_data='list_subjects_by_group')],
            [InlineKeyboardButton("➕ Добавить предмет для группы", callback_data='add_subject')],
            [InlineKeyboardButton("🗑️ Удалить предмет из группы", callback_data='delete_subject')],
            # get_back_button('main')[0]
        ]
        
        await query.edit_message_text(
            "📚 Управление предметами\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MANAGE_SUBJECTS
    
    async def manage_subjects_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка действий управления предметами"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == 'list_subjects_by_group':
            await self.show_groups_for_subjects_list(query)
            return MANAGE_SUBJECTS
            
        elif data == 'add_subject':
            await self.show_groups_for_subject_addition(query)
            return SELECT_GROUP_FOR_SUBJECT
            
        elif data == 'delete_subject':
            await self.show_groups_for_subject_deletion(query)
            return DELETE_SUBJECT
            
        elif data == 'back_to_main':
            from .base import BaseHandlers
            base_handlers = BaseHandlers()
            await base_handlers.back_to_main_menu(query)
            return ConversationHandler.END
            
        return MANAGE_SUBJECTS

    async def show_groups_for_subjects_list(self, query):
        """Показать группы для просмотра предметов"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM groups ORDER BY name")
                groups = cur.fetchall()
                
                if groups:
                    keyboard = []
                    for group in groups:
                        keyboard.append([InlineKeyboardButton(group['name'], callback_data=f'list_subjects_group_{group["id"]}')])
                    
                    keyboard.append(get_back_button('main'))
                    
                    await query.edit_message_text(
                        "👥 Выберите группу для просмотра предметов:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.edit_message_text("📝 Группы не найдены")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении групп: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")

    async def show_subjects_for_group(self, query):
        """Показать предметы для выбранной группы"""
        if query.data.startswith('list_subjects_group_'):
            group_id = int(query.data.split('_')[3])
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Получаем название группы
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                    
                    # Получаем предметы группы
                    cur.execute("""
                        SELECT s.id, s.name 
                        FROM subjects s
                        JOIN group_subjects gs ON s.id = gs.subject_id
                        WHERE gs.group_id = ?
                        ORDER BY s.name
                    """, (group_id,))
                    
                    subjects = cur.fetchall()
                    
                    # Получаем количество занятий по каждому предмету
                    subject_stats = {}
                    for subject in subjects:
                        cur.execute("""
                            SELECT COUNT(*) FROM lessons l
                            JOIN group_subjects gs ON l.group_subject_id = gs.id
                            WHERE gs.group_id = ? AND gs.subject_id = ?
                        """, (group_id, subject['id']))
                        lesson_count = cur.fetchone()[0]
                        subject_stats[subject['id']] = lesson_count
                    
                    if subjects:
                        text = f"📚 Предметы группы {group_name}:\n\n"
                        for subject in subjects:
                            lesson_count = subject_stats.get(subject['id'], 0)
                            text += f"• {subject['name']} - {lesson_count} занятий\n"
                    else:
                        text = f"📝 В групке {group_name} нет предметов"
                    
                    keyboard = [
                        [InlineKeyboardButton("🔙 К выбору группы", callback_data='list_subjects_by_group')],
                        get_main_menu_button()
                    ]
                    
                    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                        
            except Exception as e:
                logger.error(f"Ошибка при получении предметов: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке данных")

    async def show_groups_for_subject_addition(self, query):
        """Показать группы для добавления предмета"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM groups ORDER BY name")
                groups = cur.fetchall()
                
                if groups:
                    keyboard = []
                    for group in groups:
                        keyboard.append([InlineKeyboardButton(group['name'], callback_data=f'add_subject_group_{group["id"]}')])
                    
                    keyboard.append(get_back_button('main'))
                    
                    await query.edit_message_text(
                        "👥 Выберите группу для добавления предмета:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return SELECT_GROUP_FOR_SUBJECT
                else:
                    await query.edit_message_text("📝 Группы не найдены")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении групп: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")

    async def select_group_for_subject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора группы для добавления предмета"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('add_subject_group_'):
            group_id = int(query.data.split('_')[3])
            context.user_data['subject_group_id'] = group_id
            
            # Получаем название группы
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                
                await query.edit_message_text(
                    f"📚 Добавление предмета для группы {group_name}\n\n"
                    f"Введите название предмета:"
                )
                return ADD_SUBJECT_NAME
                    
            except Exception as e:
                logger.error(f"Ошибка при получении данных группы: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке данных")
        
        return SELECT_GROUP_FOR_SUBJECT

    async def add_subject_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление нового предмета для группы"""
        subject_name = update.message.text.strip()
        group_id = context.user_data['subject_group_id']
        
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                
                # Получаем название группы
                cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                group_name = cur.fetchone()['name']
                
                # Сначала находим или создаем предмет
                cur.execute("SELECT id FROM subjects WHERE name = ?", (subject_name,))
                subject = cur.fetchone()
                
                if subject:
                    subject_id = subject['id']
                else:
                    cur.execute("INSERT INTO subjects (name) VALUES (?)", (subject_name,))
                    subject_id = cur.lastrowid
                
                # Проверяем, не привязан ли уже этот предмет к группе
                cur.execute("SELECT id FROM group_subjects WHERE group_id = ? AND subject_id = ?", (group_id, subject_id))
                if cur.fetchone():
                    await update.message.reply_text("❌ Этот предмет уже добавлен для данной группы!")
                    return ConversationHandler.END
                
                # Связываем предмет с группой
                cur.execute("INSERT INTO group_subjects (group_id, subject_id) VALUES (?, ?)", (group_id, subject_id))
                conn.commit()
            
            keyboard = [
                [InlineKeyboardButton("🔙 К управлению предметами", callback_data='back_to_subjects_management')],
                get_main_menu_button()
            ]
            
            await update.message.reply_text(
                f"✅ Предмет '{subject_name}' успешно добавлен для группы {group_name}!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении предмета: {e}")
            await update.message.reply_text("❌ Ошибка при добавлении предмета")
        
        return ConversationHandler.END

    async def show_groups_for_subject_deletion(self, query):
        """Показать группы для удаления предмета"""
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM groups ORDER BY name")
                groups = cur.fetchall()
                
                if groups:
                    keyboard = []
                    for group in groups:
                        keyboard.append([InlineKeyboardButton(group['name'], callback_data=f'delete_subject_group_{group["id"]}')])
                    
                    keyboard.append(get_back_button('main'))
                    
                    await query.edit_message_text(
                        "👥 Выберите группу для удаления предмета:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return DELETE_SUBJECT
                else:
                    await query.edit_message_text("📝 Группы не найдены")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении групп: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных")

    async def delete_subject_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение удаления предмета из группы"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('delete_subject_group_'):
            group_id = int(query.data.split('_')[3])
            context.user_data['delete_subject_group_id'] = group_id
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Получаем название группы
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                    
                    # Получаем предметы группы
                    cur.execute("""
                        SELECT s.id, s.name 
                        FROM subjects s
                        JOIN group_subjects gs ON s.id = gs.subject_id
                        WHERE gs.group_id = ?
                        ORDER BY s.name
                    """, (group_id,))
                    
                    subjects = cur.fetchall()
                    
                    if subjects:
                        keyboard = []
                        for subject in subjects:
                            keyboard.append([InlineKeyboardButton(subject['name'], callback_data=f'delete_this_subject_{subject["id"]}')])
                        
                        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_subjects_management')])
                        
                        await query.edit_message_text(
                            f"🗑️ Выберите предмет для удаления из группы {group_name}:",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_subjects_management')]]
                        await query.edit_message_text(
                            f"📝 В группе {group_name} нет предметов для удаления",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        
            except Exception as e:
                logger.error(f"Ошибка при получении предметов: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке данных")
        
        elif query.data.startswith('delete_this_subject_'):
            subject_id = int(query.data.split('_')[2])
            group_id = context.user_data['delete_subject_group_id']
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Получаем названия
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                    
                    cur.execute("SELECT name FROM subjects WHERE id = ?", (subject_id,))
                    subject_name = cur.fetchone()['name']
                    
                    # Проверяем, есть ли занятия по этому предмету в группе
                    cur.execute("""
                        SELECT COUNT(*) FROM lessons l
                        JOIN group_subjects gs ON l.group_subject_id = gs.id
                        WHERE gs.group_id = ? AND gs.subject_id = ?
                    """, (group_id, subject_id))
                    
                    lesson_count = cur.fetchone()[0]
                    
                    if lesson_count > 0:
                        keyboard = [
                            [InlineKeyboardButton("✅ Удалить с занятиями", callback_data=f'confirm_delete_subject_with_lessons_{subject_id}')],
                            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_delete_subject')]
                        ]
                        
                        await query.edit_message_text(
                            f"⚠️ По предмету '{subject_name}' в группе {group_name} есть {lesson_count} занятий!\n\n"
                            f"Вы уверены, что хотите удалить предмет вместе с занятиями?",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        keyboard = [
                            [InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_subject_{subject_id}')],
                            [InlineKeyboardButton("❌ Нет, отмена", callback_data='cancel_delete_subject')]
                        ]
                        
                        await query.edit_message_text(
                            f"⚠️ Вы уверены, что хотите удалить предмет '{subject_name}' из группы {group_name}?",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    
                    return DELETE_SUBJECT
                    
            except Exception as e:
                logger.error(f"Ошибка при получении данных: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке данных")
        
        elif query.data.startswith('confirm_delete_subject_'):
            subject_id = int(query.data.split('_')[3])
            group_id = context.user_data['delete_subject_group_id']
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Получаем названия
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                    
                    cur.execute("SELECT name FROM subjects WHERE id = ?", (subject_id,))
                    subject_name = cur.fetchone()['name']
                    
                    # Удаляем связь предмета с группой
                    cur.execute("""
                        DELETE FROM group_subjects 
                        WHERE group_id = ? AND subject_id = ?
                    """, (group_id, subject_id))
                    
                    conn.commit()
                
                keyboard = [
                    [InlineKeyboardButton("🔙 К управлению предметами", callback_data='back_to_subjects_management')],
                    get_main_menu_button()
                ]
                
                await query.edit_message_text(
                    f"✅ Предмет '{subject_name}' удален из группы {group_name}!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                    
            except Exception as e:
                logger.error(f"Ошибка при удалении предмета: {e}")
                await query.edit_message_text("❌ Ошибка при удалении предмета")
        
        elif query.data == 'cancel_delete_subject':
            await self.start_subject_management(update, context)
            return MANAGE_SUBJECTS
        
        return ConversationHandler.END