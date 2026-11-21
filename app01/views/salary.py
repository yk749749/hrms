# app01/views/salary.py
"""薪资管理（T7）：CRUD + 月份/员工筛选 + 当月总额统计。"""

import logging
from decimal import Decimal

from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from app01 import models
from app01.forms import SalaryModelForm
from app01.utils.decorators import require_perm
from app01.utils.pagination import Pagination
from app01.utils.scope import salary_queryset_for

logger = logging.getLogger("hrms")


@require_perm("salary:view")
def salary_list(request):
    """薪资列表：按月份 + 员工姓名筛选，并统计选定月份的薪资总额。"""
    queryset = salary_queryset_for(request.user).order_by("-month", "-id")

    month = request.GET.get("month", "").strip() or timezone.localdate().strftime("%Y-%m")
    if len(month) == 7:
        queryset = queryset.filter(month=month)

    keyword = request.GET.get("q", "").strip()
    if keyword:
        queryset = queryset.filter(employee__name__icontains=keyword)

    # 统计：总额 / 人均 / 最高 / 最低 / 人数
    # 注意：别名不能与字段名 total 相同，否则 Avg('total') 会被解析成聚合套聚合
    summary = queryset.aggregate(
        sum_total=Sum("total"),
        avg_total=Avg("total"),
        max_total=Max("total"),
        min_total=Min("total"),
        count=Count("id"),
    )
    summary = {k: (v if v is not None else Decimal("0.00")) for k, v in summary.items()}

    page_object = Pagination(request, queryset, page_size=10)
    context = {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(always_show=True),
        "total_count": page_object.total_count,
        "month": month,
        "keyword": keyword,
        "summary": summary,
        "available_months": self_service_months(),
    }
    return render(request, "salary/list.html", context)


def self_service_months():
    """下拉框用的月份列表（最近 12 个月 + 库中已有月份，倒序）。"""
    months = set(
        models.Salary.objects.values_list("month", flat=True).distinct()
    )
    today = timezone.localdate()
    y, m = today.year, today.month
    for _ in range(12):
        months.add(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return sorted(months, reverse=True)


@require_perm("salary:add")
def salary_add(request):
    """录入薪资：``commit=False`` 先算出实发再保存，保证前后端一致。"""
    if request.method == "GET":
        initial = {"month": timezone.localdate().strftime("%Y-%m")}
        return render(
            request,
            "salary/change.html",
            {"form": SalaryModelForm(initial=initial), "title": "录入薪资"},
        )

    form = SalaryModelForm(data=request.POST)
    if form.is_valid():
        record = form.save(commit=False)
        record.total = record.compute_total()  # 实发 = 基本 + 奖金 - 扣款
        record.save()
        logger.info(
            "新增薪资 employee=%s month=%s total=%s by=%s",
            record.employee, record.month, record.total, request.user.username,
        )
        return redirect("/salary/list/")
    return render(request, "salary/change.html", {"form": form, "title": "录入薪资"})


@require_perm("salary:edit")
def salary_edit(request, nid):
    """修改薪资。"""
    row_object = models.Salary.objects.filter(id=nid).first()
    if not row_object:
        return redirect("/salary/list/")

    if request.method == "GET":
        return render(
            request,
            "salary/change.html",
            {"form": SalaryModelForm(instance=row_object), "title": "修改薪资", "row_object": row_object},
        )

    form = SalaryModelForm(data=request.POST, instance=row_object)
    if form.is_valid():
        record = form.save(commit=False)
        record.total = record.compute_total()
        record.save()
        return redirect("/salary/list/")
    return render(
        request,
        "salary/change.html",
        {"form": form, "title": "修改薪资", "row_object": row_object},
    )


@require_perm("salary:delete")
def salary_delete(request):
    """删除薪资记录。"""
    nid = request.GET.get("nid") or request.POST.get("nid")
    models.Salary.objects.filter(id=nid).delete()
    return redirect("/salary/list/")
