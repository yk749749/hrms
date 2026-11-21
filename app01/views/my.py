# app01/views/my.py
"""普通员工自助区（只读）：我的档案 / 我的考勤 / 我的薪资。"""

from django.shortcuts import redirect, render

from app01.utils.decorators import require_perm


@require_perm("self:view")
def my_profile(request):
    """我的档案。"""
    employee = getattr(request.user, "employee", None)
    if not employee:
        return render(request, "my/no_employee.html")
    return render(request, "my/profile.html", {"employee": employee})


@require_perm("self:view")
def my_attendance(request):
    """我的考勤（当月）。"""
    employee = getattr(request.user, "employee", None)
    if not employee:
        return render(request, "my/no_employee.html")

    from django.utils import timezone

    month = request.GET.get("month", "").strip() or timezone.localdate().strftime("%Y-%m")
    queryset = employee.attendances.filter(date__year=month[:4], date__month=month[5:7]).order_by("-date")
    summary = {
        "on_time": queryset.filter(status=1).count(),
        "late": queryset.filter(status=2).count(),
        "early": queryset.filter(status=3).count(),
        "absent": queryset.filter(status=4).count(),
        "late_early": queryset.filter(status=5).count(),
    }
    return render(
        request,
        "my/attendance.html",
        {"queryset": queryset, "month": month, "summary": summary, "employee": employee},
    )


@require_perm("self:view")
def my_salary(request):
    """我的薪资（全部月份，最新在前）。"""
    employee = getattr(request.user, "employee", None)
    if not employee:
        return render(request, "my/no_employee.html")
    queryset = employee.salaries.all()
    total = sum((item.total for item in queryset), start=0)
    return render(
        request,
        "my/salary.html",
        {"queryset": queryset, "employee": employee, "total": total},
    )
