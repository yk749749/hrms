# app01/views/__init__.py
"""视图包：按业务模块拆分，并在这里统一导出。

``hrms/urls.py`` 既可以直接 ``from app01.views import employee``，
也可以 ``from app01.views.employee import employee_list``。
"""

from app01.views.account import image_code, login, logout
from app01.views.ai import (
    ai_page,
    chat,
    chat_stream,
    data_comment,
    generate_jd,
    knowledge_qa,
)
from app01.views.announcement import (
    announcement_add,
    announcement_delete,
    announcement_detail,
    announcement_edit,
    announcement_list,
    announcement_toggle_top,
)
from app01.views.attendance import (
    attendance_add,
    attendance_delete,
    attendance_edit,
    attendance_list,
)
from app01.views.depart import depart_add, depart_delete, depart_edit, depart_list
from app01.views.employee import (
    employee_add,
    employee_delete,
    employee_detail,
    employee_edit,
    employee_list,
)
from app01.views.home import index
from app01.views.my import my_attendance, my_profile, my_salary
from app01.views.salary import salary_add, salary_delete, salary_edit, salary_list
from app01.views.stats import attendance_chart, depart_chart, salary_trend, stats_page
from app01.views.system import (
    permission_list,
    role_add,
    role_delete,
    role_edit,
    role_list,
    user_add,
    user_delete,
    user_edit,
    user_list,
    user_reset_password,
)
from app01.views.task import task_add_ajax, task_delete, task_list, task_toggle_ajax

__all__ = [
    "index",
    "login",
    "logout",
    "image_code",
    "depart_list", "depart_add", "depart_edit", "depart_delete",
    "employee_list", "employee_add", "employee_edit", "employee_delete", "employee_detail",
    "attendance_list", "attendance_add", "attendance_edit", "attendance_delete",
    "salary_list", "salary_add", "salary_edit", "salary_delete",
    "announcement_list", "announcement_add", "announcement_edit", "announcement_delete",
    "announcement_detail", "announcement_toggle_top",
    "task_list", "task_add_ajax", "task_toggle_ajax", "task_delete",
    "stats_page", "depart_chart", "salary_trend", "attendance_chart",
    "user_list", "user_add", "user_edit", "user_delete", "user_reset_password",
    "role_list", "role_add", "role_edit", "role_delete", "permission_list",
    "my_profile", "my_attendance", "my_salary",
    "ai_page", "generate_jd", "knowledge_qa", "data_comment", "chat", "chat_stream",
]
