# app01/views/stats.py
"""数据统计可视化（T10）：后端 ORM 聚合，前端 ECharts 通过 AJAX 取 JSON 渲染。"""

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from app01 import models
from app01.utils.decorators import require_perm


@require_perm("stats:view")
def stats_page(request):
    """统计页面（图表数据由下面两个 AJAX 接口提供）。"""
    return render(request, "stats/index.html", {"year": timezone.localdate().year})


@require_perm("stats:view")
def depart_chart(request):
    """部门人数分布（饼图）。

    用 ``annotate(Count("employees"))`` 让数据库一次算完每个部门的人数，
    再 ``filter(value__gt=0)`` 去掉空部门（否则饼图会出现 0 值扇区）。
    """
    rows = (
        models.Department.objects.annotate(value=Count("employees"))
        .filter(value__gt=0)
        .values("title", "value")
        .order_by("-value")
    )
    data = [{"name": row["title"], "value": row["value"]} for row in rows]
    return JsonResponse({"status": True, "data": data, "total": sum(item["value"] for item in data)})


@require_perm("stats:view")
def salary_trend(request):
    """各月薪资趋势（折线/柱状图）：总额 + 人均。

    ``TruncMonth`` 只在 Date 字段上有效，这里用字符串月份 ``YYYY-MM`` 排序后聚合，
    避免依赖数据库的日期函数差异（MySQL / SQLite 都能跑）。
    """
    rows = (
        models.Salary.objects.values("month")
        .annotate(sum_total=Sum("total"), avg_total=Avg("total"), cnt=Count("id"))
        .order_by("month")
    )
    months = [row["month"] for row in rows]
    totals = [float(row["sum_total"] or 0) for row in rows]
    avgs = [round(float(row["avg_total"] or 0), 2) for row in rows]
    return JsonResponse(
        {
            "status": True,
            "data": {"months": months, "totals": totals, "avgs": avgs},
        }
    )


@require_perm("stats:view")
def attendance_chart(request):
    """最近 7 天考勤状态堆叠图。

    实现方式：先算出 7 天的日期列表，再按 ``date`` 分组统计每种状态的数量，
    最后按“状态”而不是“日期”组织成 ECharts 需要的 series（每个状态一条柱子），
    这样同一天的五种状态会堆叠在同一根柱子上。
    """
    today = timezone.localdate()
    days = [today.fromordinal(today.toordinal() - i) for i in range(6, -1, -1)]
    labels = [d.strftime("%m-%d") for d in days]

    series_map = {status: [] for status, _ in models.Attendance.STATUS_CHOICES}
    for day in days:
        counts = dict(
            models.Attendance.objects.filter(date=day)
            .values_list("status")
            .annotate(c=Count("id"))
        )
        for status in series_map:
            series_map[status].append(counts.get(status, 0))

    data = [
        {"name": label, "data": series_map[status]}
        for status, label in models.Attendance.STATUS_CHOICES
    ]
    return JsonResponse({"status": True, "data": {"days": labels, "series": data}})
