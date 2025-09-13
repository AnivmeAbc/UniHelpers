import logging
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    ConversationHandler,
    MessageHandler,
    filters
)
from database import init_database
from config import BOT_TOKEN, GENERATE_REPORT, SELECT_REPORT_DATE_RANGE, SELECT_REPORT_GROUP
from handlers.base import BaseHandlers
from handlers.admin import AdminHandlers
from handlers.student import StudentHandlers
from handlers.group import GroupHandlers
from handlers.subject import SubjectHandlers
from handlers.attendance import AttendanceHandlers
from config import (
    MANAGE_STUDENTS, ADD_STUDENT_NAME, ADD_STUDENT_GROUP, EDIT_STUDENT_SELECT, DELETE_STUDENT,
    REGISTER_NAME, REGISTER_GROUP, MANAGE_GROUPS, ADD_GROUP_NAME, EDIT_GROUP_SELECT,
    EDIT_GROUP_NAME, DELETE_GROUP, SELECT_GROUP_ATTENDANCE, SELECT_SUBJECT_ATTENDANCE,
    SELECT_DATE_ATTENDANCE, MARK_STUDENTS_ATTENDANCE, MANAGE_SUBJECTS,
    ADD_SUBJECT_NAME, SELECT_GROUP_FOR_SUBJECT, DELETE_SUBJECT
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class UniHelperBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.base_handlers = BaseHandlers()
        self.admin_handlers = AdminHandlers()
        self.student_handlers = StudentHandlers()
        self.group_handlers = GroupHandlers()
        self.subject_handlers = SubjectHandlers()
        self.attendance_handlers = AttendanceHandlers()

    def setup_handlers(self):
        """Настройка обработчиков команд"""
        try:
            # 1. Основные команды
            self.application.add_handler(CommandHandler("start", self.base_handlers.start))
            self.application.add_handler(CommandHandler("help", self.base_handlers.help_command))
            self.application.add_handler(CommandHandler("cancel", self.base_handlers.cancel))
            
            # 2. ConversationHandler для регистрации студентов
            student_registration_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(self.student_handlers.start_student_registration, pattern='^register_student$')],
                states={
                    REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.student_handlers.register_student_name)],
                    REGISTER_GROUP: [CallbackQueryHandler(self.student_handlers.register_student_group, pattern='^register_group_|^cancel_register$')]
                },
                fallbacks=[CommandHandler('cancel', self.base_handlers.cancel)],
                per_message=False
            )
            self.application.add_handler(student_registration_handler)
            
            # 3. ConversationHandler для управления студентами
            student_management_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(self.admin_handlers.start_student_management, pattern='^manage_students$')],
                states={
                    MANAGE_STUDENTS: [CallbackQueryHandler(self.admin_handlers.manage_students_action)],
                    ADD_STUDENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_handlers.add_student_name)],
                    ADD_STUDENT_GROUP: [CallbackQueryHandler(self.admin_handlers.add_student_group, pattern='^group_|^cancel_add$')],
                    EDIT_STUDENT_SELECT: [CallbackQueryHandler(self.admin_handlers.edit_student_select, pattern='^edit_|^back_to_management$')],
                    DELETE_STUDENT: [CallbackQueryHandler(self.admin_handlers.delete_student_confirm, pattern='^delete_|^confirm_delete_|^cancel_delete$')]
                },
                fallbacks=[CommandHandler('cancel', self.base_handlers.cancel)],
                per_message=False
            )
            self.application.add_handler(student_management_handler)
            
            # 4. ConversationHandler для управления группами
            group_management_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(self.group_handlers.start_group_management, pattern='^manage_groups$')],
                states={
                    MANAGE_GROUPS: [CallbackQueryHandler(self.group_handlers.manage_groups_action)],
                    ADD_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.group_handlers.add_group_name)],
                    EDIT_GROUP_SELECT: [CallbackQueryHandler(self.group_handlers.edit_group_select, pattern='^edit_group_|^back_to_groups_management$')],
                    EDIT_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.group_handlers.edit_group_name)],
                    DELETE_GROUP: [CallbackQueryHandler(self.group_handlers.delete_group_confirm, pattern='^delete_group_|^confirm_delete_group_|^cancel_delete_group$')]
                },
                fallbacks=[CommandHandler('cancel', self.base_handlers.cancel)],
                per_message=False
            )
            self.application.add_handler(group_management_handler)
            
            # 5. ConversationHandler для управления предметами
            subject_management_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(self.subject_handlers.start_subject_management, pattern='^manage_subjects$')],
                states={
                    MANAGE_SUBJECTS: [CallbackQueryHandler(self.subject_handlers.manage_subjects_action)],
                    SELECT_GROUP_FOR_SUBJECT: [CallbackQueryHandler(self.subject_handlers.select_group_for_subject, pattern='^add_subject_group_')],
                    ADD_SUBJECT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.subject_handlers.add_subject_name)],
                    DELETE_SUBJECT: [CallbackQueryHandler(self.subject_handlers.delete_subject_confirm, pattern='^delete_subject_group_|^delete_this_subject_|^confirm_delete_subject_|^cancel_delete_subject$')]
                },
                fallbacks=[CommandHandler('cancel', self.base_handlers.cancel)],
                per_message=False
            )
            self.application.add_handler(subject_management_handler)
            
            # 6. ConversationHandler для посещаемости
            attendance_marking_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(self.attendance_handlers.start_attendance, pattern='^start_attendance$')],
                states={
                    SELECT_GROUP_ATTENDANCE: [CallbackQueryHandler(self.attendance_handlers.select_group_attendance, pattern='^attendance_group_|^back_to_main$')],
                    SELECT_SUBJECT_ATTENDANCE: [CallbackQueryHandler(self.attendance_handlers.select_subject_attendance, pattern='^attendance_subject_')],
                    SELECT_DATE_ATTENDANCE: [
                        CallbackQueryHandler(self.attendance_handlers.select_date_attendance, pattern='^attendance_date_|^enter_date_manually$'),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.attendance_handlers.enter_date_manually)
                    ],
                    MARK_STUDENTS_ATTENDANCE: [CallbackQueryHandler(self.attendance_handlers.mark_student_attendance, pattern='^mark_|^save_attendance$')]
                },
                fallbacks=[CommandHandler('cancel', self.base_handlers.cancel)],
                per_message=False
            )
            self.application.add_handler(attendance_marking_handler)

            # 7. ConversationHandler для генерации отчетов
            report_generation_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(self.attendance_handlers.generate_report, pattern='^generate_report$')],
                states={ 
                    SELECT_REPORT_GROUP: [CallbackQueryHandler(self.attendance_handlers.select_report_group, pattern='^report_group_')],
                    SELECT_REPORT_DATE_RANGE: [
                        CallbackQueryHandler(self.attendance_handlers.select_report_date_range, pattern='^report_period_'),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.attendance_handlers.enter_custom_date_range)
                    ],
                    GENERATE_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.attendance_handlers.generate_final_report)]
                },
                fallbacks=[CommandHandler('cancel', self.base_handlers.cancel)],
                per_message=False
            )

            self.application.add_handler(report_generation_handler)
            
            # 8. Общий обработчик кнопок (должен быть последним)
            self.application.add_handler(CallbackQueryHandler(self.simple_button_handler))
            
            logger.info("Все обработчики успешно настроены")
            
        except Exception as e:
            logger.error(f"Ошибка при настройке обработчиков: {e}")
            raise

    async def simple_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик простых кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Основные кнопки меню
        if data == 'my_attendance':
            await self.attendance_handlers.show_my_attendance(query)
        elif data == 'materials':
            await query.edit_message_text("📚 Полезные материалы будут добавлены позже")
        elif data == 'schedule':
            await query.edit_message_text("📅 Расписание будет доступно soon")
        elif data == 'help':
            await query.edit_message_text("❓ Помощь по боту будет доступна soon")
        
        # Кнопки админ-меню
        elif data == 'generate_report':
            await self.attendance_handlers.generate_report(update, context)
        elif data == 'chat_management':
            await query.edit_message_text("👥 Управление чатом - функция в разработке")
        elif data == 'manage_chats':
            await query.edit_message_text("💬 Управление чатами - доступно только админам")
        
        # Кнопки навигации
        elif data == 'back_to_main':  
            await self.base_handlers.back_to_main_menu(query)
        elif data == 'back_to_management':
            await self.base_handlers.back_to_management(query)
        elif data == 'back_to_groups_management':
            await self.base_handlers.back_to_groups_management(query)
        elif data == 'back_to_subjects_management':
            await self.base_handlers.back_to_subjects_management(query)
        
        # Кнопки управления предметами
        elif data.startswith('list_subjects_group_'):
            await self.subject_handlers.show_subjects_for_group(query)
        
        # Кнопки, которые обрабатываются ConversationHandler
        elif data in ['start_attendance', 'manage_students', 'manage_groups', 'manage_subjects', 'register_student']:
            await query.answer("Обработка запроса...")
        elif data == 'generate_report':
            await query.answer("Начинаем генерацию отчета...")
        
        else:
            await query.edit_message_text("❌ Неизвестная команда")

    def run(self):
        """Запуск бота"""
        logger.info("Бот запускается...")
        init_database()
        self.application.run_polling()

if __name__ == "__main__":
    bot = UniHelperBot(BOT_TOKEN)
    bot.setup_handlers()
    bot.run()