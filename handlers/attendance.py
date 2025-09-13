from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
import logging
from datetime import datetime, timedelta
from database import db_connection
from config import SELECT_GROUP_ATTENDANCE, SELECT_SUBJECT_ATTENDANCE, SELECT_DATE_ATTENDANCE, MARK_STUDENTS_ATTENDANCE, SELECT_REPORT_GROUP, SELECT_REPORT_DATE_RANGE, GENERATE_REPORT
from utils import check_admin_rights, get_user_role
from keyboards import get_back_button, get_main_menu_button, get_groups_keyboard
import pandas as pd
from io import BytesIO
import numpy as np

logger = logging.getLogger(__name__)

class AttendanceHandlers:
    """Обработчики для посещаемости"""
    
    async def start_attendance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса отметки посещаемости"""
        query = update.callback_query
        await query.answer()
        
        if not await check_admin_rights(query.from_user.id):
            await query.edit_message_text("❌ Доступно только администраторам")
            return ConversationHandler.END
        
        # Получаем список групп
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM groups ORDER BY name")
                groups = cur.fetchall()
                
                if not groups:
                    await query.edit_message_text("❌ В системе нет групп")
                    return ConversationHandler.END
            
            keyboard = []
            for group in groups:
                keyboard.append([InlineKeyboardButton(group['name'], callback_data=f'attendance_group_{group["id"]}')])
            
            keyboard.append(get_back_button('main'))
            
            await query.edit_message_text(
                "📊 Отметка посещаемости\n\nВыберите группу:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return SELECT_GROUP_ATTENDANCE
                
        except Exception as e:
            logger.error(f"Ошибка при получении групп: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке групп")
            return ConversationHandler.END
    
    async def select_group_attendance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор группы для посещаемости"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_main':
            from .base import BaseHandlers
            base_handlers = BaseHandlers()
            await base_handlers.back_to_main_menu(query)
            return ConversationHandler.END
        
        if query.data.startswith('attendance_group_'):
            group_id = int(query.data.split('_')[2])
            context.user_data['attendance_group_id'] = group_id
            
            # Получаем предметы для выбранной группы
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Получаем название группы
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                    
                    # Получаем предметы этой группы
                    cur.execute("""
                        SELECT s.id, s.name 
                        FROM subjects s
                        JOIN group_subjects gs ON s.id = gs.subject_id
                        WHERE gs.group_id = ?
                        ORDER BY s.name
                    """, (group_id,))
                    
                    subjects = cur.fetchall()
                    
                    if not subjects:
                        keyboard = [get_back_button('main')]
                        await query.edit_message_text(
                            f"❌ В группе {group_name} нет предметов\n\nДобавьте предметы через меню управления предметами",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        return ConversationHandler.END
                    
                    keyboard = []
                    for subject in subjects:
                        keyboard.append([InlineKeyboardButton(subject['name'], callback_data=f'attendance_subject_{subject["id"]}')])
                    
                    keyboard.append(get_back_button('main'))
                    
                    await query.edit_message_text(
                        f"📚 Выберите предмет для группы {group_name}:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return SELECT_SUBJECT_ATTENDANCE
                        
            except Exception as e:
                logger.error(f"Ошибка при получении предметов: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке предметов")
        
        return ConversationHandler.END
    
    async def select_subject_attendance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор предмета для посещаемости"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('attendance_subject_'):
            subject_id = int(query.data.split('_')[2])
            group_id = context.user_data['attendance_group_id']
            
            # Получаем group_subject_id
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    cur.execute("""
                        SELECT id FROM group_subjects 
                        WHERE group_id = ? AND subject_id = ?
                    """, (group_id, subject_id))
                    
                    group_subject = cur.fetchone()
                    if not group_subject:
                        await query.edit_message_text("❌ Ошибка: связь предмета с группой не найдена")
                        return ConversationHandler.END
                    
                    group_subject_id = group_subject['id']
                    context.user_data['attendance_group_subject_id'] = group_subject_id
                    
                    # Получаем названия для сообщения
                    cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                    group_name = cur.fetchone()['name']
                    
                    cur.execute("SELECT name FROM subjects WHERE id = ?", (subject_id,))
                    subject_name = cur.fetchone()['name']
                
                # Предлагаем выбрать дату
                today = datetime.now().strftime('%Y-%m-%d')
                keyboard = [
                    [InlineKeyboardButton("📅 Сегодня", callback_data=f'attendance_date_{today}')],
                    [InlineKeyboardButton("📅 Ввести дату вручную", callback_data='enter_date_manually')],
                    get_back_button('main')[0]
                ]
                
                await query.edit_message_text(
                    f"📅 Выберите дату занятия:\nГруппа: {group_name}\nПредмет: {subject_name}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return SELECT_DATE_ATTENDANCE
                    
            except Exception as e:
                logger.error(f"Ошибка при получении данных: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке данных")
        
        return ConversationHandler.END
    
    async def select_date_attendance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор даты для посещаемости"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('attendance_date_'):
            date_str = query.data.split('_')[2]
            context.user_data['attendance_date'] = date_str
            await self.show_students_for_attendance(query, context)
            return MARK_STUDENTS_ATTENDANCE
        
        elif query.data == 'enter_date_manually':
            await query.edit_message_text("📅 Введите дату в формате ГГГГ-ММ-ДД (например, 2024-01-15):")
            return SELECT_DATE_ATTENDANCE
        
        return ConversationHandler.END
    
    async def enter_date_manually(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка введенной даты"""
        try:
            date_str = update.message.text.strip()
            datetime.strptime(date_str, '%Y-%m-%d')  # Проверка формата
            context.user_data['attendance_date'] = date_str
            await self.show_students_for_attendance(None, context, update)
            return MARK_STUDENTS_ATTENDANCE
        except ValueError:
            await update.message.reply_text("❌ Неверный формат дату. Используйте ГГГГ-ММ-ДД:")
            return SELECT_DATE_ATTENDANCE
    
    async def show_students_for_attendance(self, query, context, update=None):
        """Показать студентов для отметки посещаемости"""
        group_id = context.user_data['attendance_group_id']
        group_subject_id = context.user_data['attendance_group_subject_id']
        date_str = context.user_data['attendance_date']
        
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                
                # Получаем студентов группы
                cur.execute("""
                    SELECT s.id, s.full_name 
                    FROM students s 
                    WHERE s.group_id = ? 
                    ORDER BY s.full_name
                """, (group_id,))
                students = cur.fetchall()
                
                # Создаем или получаем lesson_id
                cur.execute("""
                    SELECT id FROM lessons 
                    WHERE group_subject_id = ? AND date = ?
                """, (group_subject_id, date_str))
                
                lesson = cur.fetchone()
                if lesson:
                    lesson_id = lesson['id']
                else:
                    cur.execute("""
                        INSERT INTO lessons (group_subject_id, date) 
                        VALUES (?, ?)
                    """, (group_subject_id, date_str))
                    lesson_id = cur.lastrowid
                    conn.commit()
                
                context.user_data['attendance_lesson_id'] = lesson_id
                
                # Получаем текущую посещаемость
                attendance_status = {}
                cur.execute("""
                    SELECT student_id, status FROM attendance 
                    WHERE lesson_id = ?
                """, (lesson_id,))
                
                for row in cur.fetchall():
                    attendance_status[row['student_id']] = row['status']
                
                # Получаем названия для заголовка
                cur.execute("""
                    SELECT g.name, s.name 
                    FROM group_subjects gs
                    JOIN groups g ON gs.group_id = g.id
                    JOIN subjects s ON gs.subject_id = s.id
                    WHERE gs.id = ?
                """, (group_subject_id,))
                
                group_name, subject_name = cur.fetchone()
                
                # Создаем клавиатуру для отметки - ИСПРАВЛЕНО!
                keyboard = []
                for student in students:
                    current_status = attendance_status.get(student['id'], 'not_set')
                    status_icon = '✅' if current_status == 'present' else '❌' if current_status == 'absent' else '⏰' if current_status == 'late' else '⚪'
                    
                    # Каждый студент в отдельном ряду с кнопками
                    student_row = [
                        InlineKeyboardButton(f"{status_icon} {student['full_name']}", callback_data=f'student_{student["id"]}')
                    ]
                    
                    # Кнопки статусов в отдельных рядах под именем студента
                    status_row = [
                        InlineKeyboardButton("✅ Присутствовал", callback_data=f'mark_present_{student["id"]}'),
                        InlineKeyboardButton("❌ Отсутствовал", callback_data=f'mark_absent_{student["id"]}'),
                        InlineKeyboardButton("⏰ Опоздал", callback_data=f'mark_late_{student["id"]}')
                    ]
                    
                    keyboard.append(student_row)
                    keyboard.append(status_row)
                
                # Кнопки сохранения и возврата
                keyboard.append([InlineKeyboardButton("💾 Сохранить посещаемость", callback_data='save_attendance')])
                keyboard.append(get_back_button('main')[0])
                
                message_text = f"📊 Отметка посещаемости\n\nГруппа: {group_name}\nПредмет: {subject_name}\nДата: {date_str}\n\nВыберите статус для каждого студента:"
                
                if query:
                    await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await update.message.reply_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard))
                    
        except Exception as e:
            logger.error(f"Ошибка при получении студентов: {e}")
            if query:
                await query.edit_message_text("❌ Ошибка при загрузке данных")
            else:
                await update.message.reply_text("❌ Ошибка при загрузке данных")
    
    async def mark_student_attendance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отметка посещаемости студента"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('mark_'):
            action, student_id = query.data.split('_')[1], int(query.data.split('_')[2])
            lesson_id = context.user_data['attendance_lesson_id']
            
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Обновляем или добавляем запись посещаемости
                    cur.execute("""
                        INSERT OR REPLACE INTO attendance (student_id, lesson_id, status)
                        VALUES (?, ?, ?)
                    """, (student_id, lesson_id, action))
                    
                    conn.commit()
                
                # Обновляем список студентов
                await self.show_students_for_attendance(query, context)
                
            except Exception as e:
                logger.error(f"Ошибка при отметке посещаемости: {e}")
                await query.answer("❌ Ошибка при сохранении")
        
        elif query.data == 'save_attendance':
            # Сохраняем и выходим
            group_id = context.user_data['attendance_group_id']
            
            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                group_name = cur.fetchone()['name']
            
            keyboard = [
                [InlineKeyboardButton("🔙 К управлению", callback_data='back_to_management')],
                get_main_menu_button()
            ]
            
            await query.edit_message_text(
                f"✅ Посещаемость для группы {group_name} сохранена!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ConversationHandler.END
        
        return MARK_STUDENTS_ATTENDANCE
    
    async def show_my_attendance(self, query):
        """Показать посещаемость студента"""
        user_id = query.from_user.id
        
        try:
            with db_connection() as conn:
                cur = conn.cursor()
                
                # Получаем информацию о студенте
                cur.execute("""
                    SELECT s.id, s.full_name, g.name, s.group_id
                    FROM students s 
                    JOIN groups g ON s.group_id = g.id 
                    WHERE s.telegram_id = ?
                """, (user_id,))
                
                student = cur.fetchone()
                if not student:
                    await query.edit_message_text("❌ Вы не зарегистрированы как студент")
                    return
                
                # Получаем статистику посещаемости
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_lessons,
                        SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present,
                        SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as absent,
                        SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) as late
                    FROM lessons l
                    JOIN group_subjects gs ON l.group_subject_id = gs.id
                    LEFT JOIN attendance a ON l.id = a.lesson_id AND a.student_id = ?
                    WHERE gs.group_id = ?
                """, (student['id'], student['group_id']))
                
                stats = cur.fetchone()
                total, present, absent, late = stats if stats else (0, 0, 0, 0)
                
                # Получаем последние занятия
                cur.execute("""
                    SELECT s.name, l.date, a.status
                    FROM lessons l
                    JOIN group_subjects gs ON l.group_subject_id = gs.id
                    JOIN subjects s ON gs.subject_id = s.id
                    LEFT JOIN attendance a ON l.id = a.lesson_id AND a.student_id = ?
                    WHERE gs.group_id = ?
                    ORDER BY l.date DESC
                    LIMIT 10
                """, (student['id'], student['group_id']))
                
                recent_lessons = cur.fetchall()
                
                # Формируем сообщение
                text = f"📊 Ваша посещаемость\n\n👤 {student['full_name']}\n📚 Группа: {student['name']}\n\n"
                text += f"📈 Статистика:\n"
                text += f"• Всего занятий: {total}\n"
                if total > 0:
                    attendance_percent = (present / total) * 100
                    text += f"• Присутствовал: {present} ({attendance_percent:.1f}%)\n"
                else:
                    text += f"• Присутствовал: 0\n"
                text += f"• Отсутствовал: {absent}\n"
                text += f"• Опоздал: {late}\n\n"
                
                text += "📅 Последние занятия:\n"
                for lesson in recent_lessons:
                    status_icon = '✅' if lesson['status'] == 'present' else '❌' if lesson['status'] == 'absent' else '⏰' if lesson['status'] == 'late' else '❓'
                    text += f"• {lesson['date']} - {lesson['name']} {status_icon}\n"
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Обновить", callback_data='my_attendance')],
                    get_main_menu_button()
                ]
                
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                
        except Exception as e:
            logger.error(f"Ошибка при получении посещаемости: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке данных посещаемости")
    
    async def generate_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Начало процесса генерации отчета"""
            query = update.callback_query
            await query.answer()
            
            if not await check_admin_rights(query.from_user.id):
                await query.edit_message_text("❌ Доступно только администраторам")
                return ConversationHandler.END
            
            # Получаем список групп
            try:
                with db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id, name FROM groups ORDER BY name")
                    groups = cur.fetchall()
                    
                    if not groups:
                        await query.edit_message_text("❌ В системе нет групп")
                        return ConversationHandler.END
                
                keyboard = []
                for group in groups:
                    keyboard.append([InlineKeyboardButton(group['name'], callback_data=f'report_group_{group["id"]}')])
                
                keyboard.append(get_back_button('main'))
                
                await query.edit_message_text(
                    "📈 Генерация отчета\n\nВыберите группу:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return SELECT_REPORT_GROUP
                    
            except Exception as e:
                logger.error(f"Ошибка при получении групп: {e}")
                await query.edit_message_text("❌ Ошибка при загрузке групп")
                return ConversationHandler.END
        
    async def select_report_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор группы для отчета"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_main':
            from .base import BaseHandlers
            base_handlers = BaseHandlers()
            await base_handlers.back_to_main_menu(query)
            return ConversationHandler.END
        
        if query.data.startswith('report_group_'):
            group_id = int(query.data.split('_')[2])
            context.user_data['report_group_id'] = group_id
            
            # Предлагаем выбрать период
            today = datetime.now()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            keyboard = [
                [InlineKeyboardButton("📅 За последнюю неделю", callback_data=f'report_period_week_{group_id}')],
                [InlineKeyboardButton("📅 За последний месяц", callback_data=f'report_period_month_{group_id}')],
                [InlineKeyboardButton("📅 За все время", callback_data=f'report_period_all_{group_id}')],
                [InlineKeyboardButton("📅 Выбрать даты", callback_data=f'report_period_custom_{group_id}')],
                get_back_button('main')[0]
            ]
            
            await query.edit_message_text(
                "📅 Выберите период для отчета:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return SELECT_REPORT_DATE_RANGE
        
        return ConversationHandler.END

    async def select_report_date_range(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора периода отчета"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('report_period_'):
            parts = query.data.split('_')
            period_type = parts[2]
            group_id = int(parts[3])
            
            today = datetime.now()
            start_date = None
            end_date = today
            
            if period_type == 'week':
                start_date = today - timedelta(days=7)
            elif period_type == 'month':
                start_date = today - timedelta(days=30)
            elif period_type == 'all':
                start_date = datetime(2020, 1, 1)  # Very old date to get all records
            elif period_type == 'custom':
                await query.edit_message_text("📅 Введите начальную дату в формате ГГГГ-ММ-ДД:")
                return SELECT_REPORT_DATE_RANGE
            
            context.user_data['report_start_date'] = start_date
            context.user_data['report_end_date'] = end_date
            
            # Генерируем отчет
            await self.generate_excel_report(query, context, group_id, start_date, end_date)
            return ConversationHandler.END
        
        return ConversationHandler.END

    async def enter_custom_date_range(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода пользовательского диапазона дат"""
        try:
            date_str = update.message.text.strip()
            start_date = datetime.strptime(date_str, '%Y-%m-%d')
            
            context.user_data['report_start_date'] = start_date
            await update.message.reply_text("📅 Введите конечную дату в формате ГГГГ-ММ-ДД (или нажмите /cancel для отмены):")
            return GENERATE_REPORT
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД:")
            return SELECT_REPORT_DATE_RANGE

    async def generate_final_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Генерация отчета с пользовательскими датами"""
        try:
            end_date_str = update.message.text.strip()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            start_date = context.user_data['report_start_date']
            group_id = context.user_data['report_group_id']
            
            await self.generate_excel_report(None, context, group_id, start_date, end_date, update)
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД:")
            return GENERATE_REPORT

    async def generate_excel_report(self, query, context, group_id, start_date, end_date, update=None):
        """Генерация Excel отчета"""
        try:
            with db_connection() as conn:
                # Получаем название группы
                cur = conn.cursor()
                cur.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
                group_name = cur.fetchone()['name']
                
                # Форматируем даты для SQL запроса
                start_date_str = start_date.strftime('%Y-%m-%d') if start_date else '2000-01-01'
                end_date_str = end_date.strftime('%Y-%m-%d') if end_date else '2100-01-01'
                
                # Основные данные посещаемости
                attendance_df = pd.read_sql(f"""
                    SELECT 
                        g.name as group_name,
                        s.full_name as student_name,
                        sub.name as subject_name,
                        l.date as lesson_date,
                        CASE 
                            WHEN a.status = 'present' THEN 'Присутствовал'
                            WHEN a.status = 'absent' THEN 'Отсутствовал'
                            WHEN a.status = 'late' THEN 'Опоздал'
                            ELSE 'Не отмечен'
                        END as attendance_status,
                        CASE 
                            WHEN a.status = 'present' THEN 1
                            WHEN a.status = 'absent' THEN 0
                            WHEN a.status = 'late' THEN 0.5
                            ELSE NULL
                        END as attendance_score
                    FROM lessons l
                    JOIN group_subjects gs ON l.group_subject_id = gs.id
                    JOIN groups g ON gs.group_id = g.id
                    JOIN subjects sub ON gs.subject_id = sub.id
                    JOIN students s ON s.group_id = g.id
                    LEFT JOIN attendance a ON l.id = a.lesson_id AND a.student_id = s.id
                    WHERE g.id = ? 
                    AND l.date BETWEEN ? AND ?
                    ORDER BY s.full_name, l.date
                """, conn, params=(group_id, start_date_str, end_date_str))
                
                if attendance_df.empty:
                    if query:
                        await query.edit_message_text("📊 Нет данных за выбранный период")
                    else:
                        await update.message.reply_text("📊 Нет данных за выбранный период")
                    return
                
                # Создаем Excel файл в памяти
                output = BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Лист с детальной посещаемостью
                    attendance_df.to_excel(writer, sheet_name='Детальная посещаемость', index=False)
                    
                    # Лист со статистикой по студентам
                    student_stats = attendance_df.groupby(['student_name', 'attendance_status']).size().unstack(fill_value=0)
                    student_stats['Всего занятий'] = student_stats.sum(axis=1)
                    student_stats['Процент посещаемости'] = (
                        (student_stats.get('Присутствовал', 0) + student_stats.get('Опоздал', 0) * 0.5) / 
                        student_stats['Всего занятий'] * 100
                    ).round(1)
                    student_stats.to_excel(writer, sheet_name='Статистика по студентам')
                    
                    # Лист со статистикой по предметам
                    subject_stats = attendance_df.groupby(['subject_name', 'attendance_status']).size().unstack(fill_value=0)
                    subject_stats['Всего занятий'] = subject_stats.sum(axis=1)
                    subject_stats.to_excel(writer, sheet_name='Статистика по предметам')
                    
                    # Лист с общей сводкой
                    summary_data = {
                        'Параметр': ['Группа', 'Период отчета', 'Всего занятий', 'Всего студентов', 'Средняя посещаемость'],
                        'Значение': [
                            group_name,
                            f'{start_date_str} - {end_date_str}',
                            len(attendance_df['lesson_date'].unique()),
                            attendance_df['student_name'].nunique(),
                            f"{student_stats['Процент посещаемости'].mean():.1f}%"
                        ]
                    }
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Общая сводка', index=False)
                
                output.seek(0)
                
                # Формируем название файла
                filename = f"отчет_{group_name}_{start_date_str}_{end_date_str}.xlsx"
                
                if query:
                    await query.message.reply_document(
                        document=output,
                        filename=filename,
                        caption=f'📊 Отчет по посещаемости\nГруппа: {group_name}\nПериод: {start_date_str} - {end_date_str}'
                    )
                else:
                    await update.message.reply_document(
                        document=output,
                        filename=filename,
                        caption=f'📊 Отчет по посещаемости\nГруппа: {group_name}\nПериод: {start_date_str} - {end_date_str}'
                    )
                
        except Exception as e:
            logger.error(f"Ошибка генерации отчета: {e}")
            error_msg = "❌ Ошибка при генерации отчета"
            if query:
                await query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)

    async def generate_quick_report(self, query):
        """Быстрая генерация отчета (без выбора параметров)"""
        try:
            with db_connection() as conn:
                # Получаем последние 30 дней данных
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                
                # Сводка по всем группам
                summary_df = pd.read_sql("""
                    SELECT 
                        g.name as group_name,
                        COUNT(DISTINCT l.id) as total_lessons,
                        COUNT(DISTINCT s.id) as total_students,
                        ROUND(SUM(CASE WHEN a.status = 'present' THEN 1 
                                        WHEN a.status = 'late' THEN 0.5 
                                        ELSE 0 END) * 100.0 / COUNT(a.id), 1) as attendance_percent
                    FROM groups g
                    LEFT JOIN students s ON g.id = s.group_id
                    LEFT JOIN group_subjects gs ON g.id = gs.group_id
                    LEFT JOIN lessons l ON gs.id = l.group_subject_id 
                        AND l.date BETWEEN ? AND ?
                    LEFT JOIN attendance a ON l.id = a.lesson_id AND a.student_id = s.id
                    GROUP BY g.id, g.name
                    ORDER BY g.name
                """, conn, params=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                if summary_df.empty:
                    await query.edit_message_text("📊 Нет данных для отчета")
                    return
                
                # Создаем простой текстовый отчет
                report_text = "📊 Сводка по посещаемости (последние 30 дней):\n\n"
                
                for _, row in summary_df.iterrows():
                    report_text += f"👥 {row['group_name']}:\n"
                    report_text += f"   • Занятий: {row['total_lessons']}\n"
                    report_text += f"   • Студентов: {row['total_students']}\n"
                    report_text += f"   • Посещаемость: {row['attendance_percent']}%\n\n"
                
                keyboard = [
                    [InlineKeyboardButton("📊 Подробный отчет", callback_data='generate_report')],
                    get_main_menu_button()
                ]
                
                await query.edit_message_text(report_text, reply_markup=InlineKeyboardMarkup(keyboard))
                
        except Exception as e:
            logger.error(f"Ошибка быстрой генерации отчета: {e}")
            await query.edit_message_text("❌ Ошибка при генерации отчета")