import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_NAME = 'university_bot.db'

# Состояния для ConversationHandler
(
    # Основные состояния
    SELECTING_ACTION, SELECTING_SUBJECT, SELECTING_DATE, MARKING_ATTENDANCE,
    
    # Управление студентами
    MANAGE_STUDENTS, ADD_STUDENT_NAME, ADD_STUDENT_GROUP, EDIT_STUDENT_SELECT,
    EDIT_STUDENT_NAME, EDIT_STUDENT_GROUP, DELETE_STUDENT,
    
    # Регистрация студента
    REGISTER_NAME, REGISTER_GROUP,
    
    # Управление группами
    MANAGE_GROUPS, ADD_GROUP_NAME, EDIT_GROUP_SELECT, EDIT_GROUP_NAME, DELETE_GROUP,
    
    # Посещаемость
    SELECT_GROUP_ATTENDANCE, SELECT_SUBJECT_ATTENDANCE, SELECT_DATE_ATTENDANCE,
    MARK_STUDENTS_ATTENDANCE,
    
    # Управление предметами
    MANAGE_SUBJECTS, ADD_SUBJECT_NAME, SELECT_GROUP_FOR_SUBJECT, DELETE_SUBJECT,

    # Составление отчета
    SELECT_REPORT_GROUP, SELECT_REPORT_DATE_RANGE, GENERATE_REPORT
) = range(29)