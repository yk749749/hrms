# app01/views/attendance.py
"""考勤管理（T6）：CRUD + 状态自动计算 + 按日期/员工筛选 + 月度统计。"""

import logging
from datetime import date

from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from app01 import models
from app01.forms import AttendanceModelForm
from app01.utils.decorators import require_perm
from app01.utils.pagination import Pagination
from app01.utils.scope import attendance_queryset_for

logger = logging.getLogger("hrms")


@require_perm("attendance:view")
def attendance_list(request):
    """考勤列表：支持按月份、员工姓名、状态筛选，并统计各状态天数。"""
    queryset = attendance_queryset_for(request.user).order_by("-date", "-id")

    month = request.GET.get("month", "").strip()
    if not month:
        month = timezone.localdate().strftime("%Y-%m")
    if len(month) == 7:
        queryset = queryset.filter(date__year=month[:4], date__month=month[5:7])

    keyword = request.GET.get("q", "").strip()
    if keyword:
        queryset = queryset.filter(employee__name__icontains=keyword)

    status = request.GET.get("status", "").strip()
    if status.isdigit():
        queryset = queryset.filter(status=int(status))

    # 当月各状态统计（一次聚合查询）
    stats = queryset.aggregate(
        on_time=Count("id", filter=Q(status=models.Attendance.STATUS_ON_TIME)),
        late=Count("id", filter=Q(status=models.Attendance.STATUS_LATE)),
        early=Count("id", filter=Q(status=models.Attendance.STATUS_EARLY)),
        absent=Count("id", filter=Q(status=models.Attendance.STATUS_ABSENT)),
        late_early=Count("id", filter=Q(status=models.Attendance.STATUS_LATE_EARLY)),
    )

    page_object = Pagination(request, queryset, page_size=10)
    context = {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(always_show=True),
        "total_count": page_object.total_count,
        "month": month,
        "keyword": keyword,
        "status": status,
        "status_choices": models.Attendance.STATUS_CHOICES,
        "stats": stats,
        "work_start": models.Attendance.WORK_START,
        "work_end": models.Attendance.WORK_END,
    }
    return render(request, "attendance/list.html", context)


@require_perm("attendance:add")
def attendance_add(request):
    """录入考勤：状态在表单 save 时按上下班时间自动计算。"""
    if request.method == "GET":
        initial = {"date": timezone.localdate()}
        return render(
            request,
            "attendance/change.html",
            {"form": AttendanceModelForm(initial=initial), "title": "录入考勤"},
        )

    form = AttendanceModelForm(data=request.POST)
    if form.is_valid():
        record = form.save()
        logger.info(
            "新增考勤 employee=%s date=%s status=%s by=%s",
            record.employee, record.date, record.get_status_display(), request.user.username,
        )
        return redirect("/attendance/list/")
    return render(request, "attendance/change.html", {"form": form, "title": "录入考勤"})


@require_perm("attendance:edit")
def attendance_edit(request, nid):
    """修改考勤：保存时状态会重新计算。"""
    row_object = models.Attendance.objects.filter(id=nid).first()
    if not row_object:
        return redirect("/attendance/list/")

    if request.method == "GET":
        return render(
            request,
            "attendance/change.html",
            {"form": AttendanceModelForm(instance=row_object), "title": "修改考勤", "row_object": row_object},
        )

    form = AttendanceModelForm(data=request.POST, instance=row_object)
    if form.is_valid():
        form.save()
        return redirect("/attendance/list/")
    return render(
        request,
        "attendance/change.html",
        {"form": form, "title": "修改考勤", "row_object": row_object},
    )


@require_perm("attendance:delete")
def attendance_delete(request):
    """删除考勤记录。"""
    nid = request.GET.get("nid") or request.POST.get("nid")
    models.Attendance.objects.filter(id=nid).delete()
    return redirect("/attendance/list/")
