# app01/views/employee.py
"""员工管理（T3）：完整 CRUD + 姓名模糊搜索 + 部门筛选 + 分页 + 头像上传。"""

import logging

from django.db.models import Q, Sum
from django.shortcuts import redirect, render

from app01 import models
from app01.forms import EmployeeModelForm
from app01.utils.decorators import require_perm
from app01.utils.pagination import Pagination
from app01.utils.scope import employee_queryset_for

logger = logging.getLogger("hrms")


@require_perm("employee:view")
def employee_list(request):
    """员工列表。

    性能（T11）：``select_related('depart')`` 把部门一起取出，列表页不再逐行查部门。
    （若不加，52 个员工会额外产生 52 条部门查询，即典型的 N+1 问题。）

    查询参数：
    - ``q``：姓名或手机号模糊匹配，用 ``Q`` 组合成 OR 条件；
    - ``depart``：部门筛选，只接受数字，避免把非法字符串拼进查询；
    - ``page``：交给 ``Pagination`` 处理，它内部会深拷贝查询串以保留上面两个条件。

    这里的 ``queryset`` 在分页前先被搜索/筛选过，所以后面的 ``aggregate`` 统计的是
    “当前筛选结果”的余额合计，而不是全表合计。
    """
    queryset = employee_queryset_for(request.user).order_by("id")

    # 姓名模糊搜索
    keyword = request.GET.get("q", "").strip()
    if keyword:
        queryset = queryset.filter(Q(name__icontains=keyword) | Q(mobile__icontains=keyword))

    # 部门筛选
    depart_id = request.GET.get("depart", "").strip()
    if depart_id.isdigit():
        queryset = queryset.filter(depart_id=int(depart_id))

    page_object = Pagination(request, queryset, page_size=8)
    context = {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(always_show=True),
        "total_count": page_object.total_count,
        "keyword": keyword,
        "depart_id": depart_id,
        "departments": models.Department.objects.order_by("id"),
        # 账户总余额（当前筛选结果）
        "account_total": queryset.aggregate(total=Sum("account"))["total"] or 0,
    }
    return render(request, "employee/list.html", context)


@require_perm("employee:view")
def employee_detail(request, nid):
    """员工详情：档案 + 最近考勤 + 最近薪资。"""
    employee = (
        models.Employee.objects.select_related("depart").filter(id=nid).first()
    )
    if not employee:
        return redirect("/employee/list/")
    context = {
        "employee": employee,
        "attendances": employee.attendances.all()[:10],
        "salaries": employee.salaries.all()[:12],
    }
    return render(request, "employee/detail.html", context)


@require_perm("employee:add")
def employee_add(request):
    """新建员工（ModelForm 校验：姓名长度 / 年龄范围 / 手机号正则且唯一）。

    两个细节：
    1. POST 时必须传 ``files=request.FILES``，否则头像文件不会进入表单；
    2. 保存成功后用 ``redirect`` 而不是直接 ``render`` 列表页（PRG 模式），
       避免用户按 F5 重复提交同一条新增请求。
    """
    if request.method == "GET":
        return render(request, "employee/change.html", {"form": EmployeeModelForm(), "title": "新建员工"})

    form = EmployeeModelForm(data=request.POST, files=request.FILES)
    if form.is_valid():
        form.save()
        logger.info("新增员工 name=%s by=%s", form.cleaned_data["name"], request.user.username)
        return redirect("/employee/list/")
    return render(request, "employee/change.html", {"form": form, "title": "新建员工"})


@require_perm("employee:edit")
def employee_edit(request, nid):
    """编辑员工。"""
    row_object = models.Employee.objects.filter(id=nid).first()
    if not row_object:
        return redirect("/employee/list/")

    if request.method == "GET":
        return render(
            request,
            "employee/change.html",
            {"form": EmployeeModelForm(instance=row_object), "title": "编辑员工", "row_object": row_object},
        )

    form = EmployeeModelForm(data=request.POST, files=request.FILES, instance=row_object)
    if form.is_valid():
        form.save()
        logger.info("编辑员工 id=%s by=%s", nid, request.user.username)
        return redirect("/employee/list/")
    return render(
        request,
        "employee/change.html",
        {"form": form, "title": "编辑员工", "row_object": row_object},
    )


@require_perm("employee:delete")
def employee_delete(request):
    """删除员工。

    同时兼容 GET 的 ``?nid=1`` 与 POST 表单的隐藏域，模板里删除按钮统一走 POST
    并携带 CSRF token（GET 只作为脚本调用的兜底），防止被跨站图片链接触发删除。
    """
    nid = request.GET.get("nid") or request.POST.get("nid")
    models.Employee.objects.filter(id=nid).delete()
    logger.info("删除员工 id=%s by=%s", nid, request.user.username)
    return redirect("/employee/list/")
