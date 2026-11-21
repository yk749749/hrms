# app01/views/home.py
"""首页仪表盘：关键指标卡片 + 最新公告 + 快捷入口。"""

from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.shortcuts import render
from django.utils import timezone

from app01 import models


def index(request):
    """首页。未登录时引导到登录页。"""
    if not request.user.is_authenticated:
        return render(request, "login.html", {"form": None})

    today = timezone.localdate()
    this_month = today.strftime("%Y-%m")

    # 员工范围：部门管理员只看本部门
    employees = models.Employee.objects.all()
    if not request.user.is_superuser and request.user.department_id and not request.user.has_perm_code("employee:add"):
        employees = employees.filter(depart_id=request.user.department_id)

    cards = {
        "employee_total": employees.count(),
        "department_total": models.Department.objects.count(),
        "attendance_today": models.Attendance.objects.filter(date=today).count(),
        "abnormal_today": models.Attendance.objects.filter(
            date=today, status__in=[2, 3, 4, 5]
        ).count(),
        "announcement_total": models.Announcement.objects.count(),
        "month_salary_total": models.Salary.objects.filter(month=this_month).aggregate(
            total=Sum("total")
        )["total"]
        or Decimal("0.00"),
    }

    # 今日考勤状态分布（给首页小图表用）
    status_counts = models.Attendance.objects.filter(date=today).values("status").annotate(c=Count("id"))
    context = {
        "cards": cards,
        "today": today,
        "this_month": this_month,
        "announcements": models.Announcement.objects.select_related("publisher")[:5],
        "status_counts": list(status_counts),
    }
    return render(request, "index.html", context)
