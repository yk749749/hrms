# app01/views/depart.py
"""部门管理（T2）：新增、列表、编辑、删除。"""

import logging

from django.db.models import Count, ProtectedError
from django.shortcuts import redirect, render

from app01 import models
from app01.forms import DepartmentModelForm
from app01.utils.decorators import require_perm
from app01.utils.pagination import Pagination

logger = logging.getLogger("hrms")


@require_perm("depart:view")
def depart_list(request):
    """部门列表：带员工人数统计与分页（select_related 无关，用 annotate 一次算出人数）。"""
    queryset = (
        models.Department.objects.annotate(emp_count=Count("employees"))
        .order_by("id")
    )
    keyword = request.GET.get("q", "").strip()
    if keyword:
        queryset = queryset.filter(title__icontains=keyword)

    page_object = Pagination(request, queryset, page_size=8)
    context = {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(always_show=True),
        "total_count": page_object.total_count,
        "keyword": keyword,
    }
    return render(request, "depart/list.html", context)


@require_perm("depart:add")
def depart_add(request):
    """新建部门。"""
    if request.method == "GET":
        return render(request, "depart/change.html", {"form": DepartmentModelForm(), "title": "新建部门"})

    form = DepartmentModelForm(data=request.POST)
    if form.is_valid():
        form.save()
        logger.info("新增部门 title=%s by=%s", form.cleaned_data["title"], request.user.username)
        return redirect("/depart/list/")
    return render(request, "depart/change.html", {"form": form, "title": "新建部门"})


@require_perm("depart:edit")
def depart_edit(request, nid):
    """编辑部门。"""
    row_object = models.Department.objects.filter(id=nid).first()
    if not row_object:
        return redirect("/depart/list/")

    if request.method == "GET":
        return render(
            request, "depart/change.html", {"form": DepartmentModelForm(instance=row_object), "title": "编辑部门"}
        )

    form = DepartmentModelForm(data=request.POST, instance=row_object)
    if form.is_valid():
        form.save()
        logger.info("编辑部门 id=%s by=%s", nid, request.user.username)
        return redirect("/depart/list/")
    return render(request, "depart/change.html", {"form": form, "title": "编辑部门"})


@require_perm("depart:delete")
def depart_delete(request):
    """删除部门：有员工时拒绝删除，避免误删数据。"""
    nid = request.GET.get("nid") or request.POST.get("nid")
    try:
        models.Department.objects.filter(id=nid).delete()
        logger.info("删除部门 id=%s by=%s", nid, request.user.username)
        return redirect("/depart/list/")
    except ProtectedError:
        logger.warning("删除部门失败（仍有员工） id=%s", nid)
        queryset = models.Department.objects.annotate(emp_count=Count("employees")).order_by("id")
        page_object = Pagination(request, queryset, page_size=8)
        return render(
            request,
            "depart/list.html",
            {
                "queryset": page_object.page_queryset,
                "page_string": page_object.html(always_show=True),
                "total_count": page_object.total_count,
                "keyword": "",
                "error": "该部门下仍有员工，请先调整员工所属部门后再删除",
            },
        )
