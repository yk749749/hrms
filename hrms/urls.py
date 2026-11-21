"""URL 路由总表。

约定：业务模块按前缀分组，视图使用 ``app01/views/<模块>.py`` 中的函数；
除登录、验证码外，所有页面都需要登录（由 AuthMiddleware 统一拦截）。
"""

from django.contrib import admin
from django.urls import include, path

from app01.views import (
    account,
    ai,
    announcement,
    attendance,
    depart,
    employee,
    home,
    my,
    salary,
    stats,
    system,
    task,
)

urlpatterns = [
    # 首页
    path("", home.index, name="index"),
    # 登录 / 注销 / 验证码
    path("login/", account.login, name="login"),
    path("logout/", account.logout, name="logout"),
    path("image/code/", account.image_code, name="image_code"),
    # 部门
    path("depart/list/", depart.depart_list, name="depart_list"),
    path("depart/add/", depart.depart_add, name="depart_add"),
    path("depart/<int:nid>/edit/", depart.depart_edit, name="depart_edit"),
    path("depart/delete/", depart.depart_delete, name="depart_delete"),
    # 员工
    path("employee/list/", employee.employee_list, name="employee_list"),
    path("employee/add/", employee.employee_add, name="employee_add"),
    path("employee/<int:nid>/edit/", employee.employee_edit, name="employee_edit"),
    path("employee/<int:nid>/detail/", employee.employee_detail, name="employee_detail"),
    path("employee/delete/", employee.employee_delete, name="employee_delete"),
    # 考勤
    path("attendance/list/", attendance.attendance_list, name="attendance_list"),
    path("attendance/add/", attendance.attendance_add, name="attendance_add"),
    path("attendance/<int:nid>/edit/", attendance.attendance_edit, name="attendance_edit"),
    path("attendance/delete/", attendance.attendance_delete, name="attendance_delete"),
    # 薪资
    path("salary/list/", salary.salary_list, name="salary_list"),
    path("salary/add/", salary.salary_add, name="salary_add"),
    path("salary/<int:nid>/edit/", salary.salary_edit, name="salary_edit"),
    path("salary/delete/", salary.salary_delete, name="salary_delete"),
    # 公告
    path("announcement/list/", announcement.announcement_list, name="announcement_list"),
    path("announcement/add/", announcement.announcement_add, name="announcement_add"),
    path("announcement/<int:nid>/edit/", announcement.announcement_edit, name="announcement_edit"),
    path("announcement/<int:nid>/detail/", announcement.announcement_detail, name="announcement_detail"),
    path("announcement/toggle-top/", announcement.announcement_toggle_top, name="announcement_toggle_top"),
    path("announcement/delete/", announcement.announcement_delete, name="announcement_delete"),
    # 任务（AJAX）
    path("task/list/", task.task_list, name="task_list"),
    path("task/add/", task.task_add_ajax, name="task_add_ajax"),
    path("task/toggle/", task.task_toggle_ajax, name="task_toggle_ajax"),
    path("task/delete/", task.task_delete, name="task_delete"),
    # 数据统计
    path("stats/", stats.stats_page, name="stats_page"),
    path("stats/depart-chart/", stats.depart_chart, name="stats_depart_chart"),
    path("stats/salary-trend/", stats.salary_trend, name="stats_salary_trend"),
    path("stats/attendance-chart/", stats.attendance_chart, name="stats_attendance_chart"),
    # 系统管理：用户 / 角色 / 权限
    path("system/user/list/", system.user_list, name="user_list"),
    path("system/user/add/", system.user_add, name="user_add"),
    path("system/user/<int:nid>/edit/", system.user_edit, name="user_edit"),
    path("system/user/<int:nid>/reset/", system.user_reset_password, name="user_reset_password"),
    path("system/user/delete/", system.user_delete, name="user_delete"),
    path("system/role/list/", system.role_list, name="role_list"),
    path("system/role/add/", system.role_add, name="role_add"),
    path("system/role/<int:nid>/edit/", system.role_edit, name="role_edit"),
    path("system/role/delete/", system.role_delete, name="role_delete"),
    path("system/permission/list/", system.permission_list, name="permission_list"),
    # 普通员工自助
    path("my/profile/", my.my_profile, name="my_profile"),
    path("my/attendance/", my.my_attendance, name="my_attendance"),
    path("my/salary/", my.my_salary, name="my_salary"),
    # AI 智能助手（页面 + 四个 JSON 接口 + 一个 SSE 接口）
    path("ai/", ai.ai_page, name="ai_page"),
    path("ai/jd/", ai.generate_jd, name="ai_jd"),
    path("ai/qa/", ai.knowledge_qa, name="ai_qa"),
    path("ai/comment/", ai.data_comment, name="ai_comment"),
    path("ai/chat/", ai.chat, name="ai_chat"),
    path("ai/chat/stream/", ai.chat_stream, name="ai_chat_stream"),
    # Django 自带后台（放在最后，避免其 catch-all 抢先匹配）
    path("admin/", admin.site.urls),
]
