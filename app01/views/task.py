# app01/views/task.py
"""任务管理（T9）：AJAX 异步提交 + JsonResponse 返回校验错误，页面不刷新。

接口协议（前后端约定）::

    成功：{"status": true, "data": {...}}
    失败：{"status": false, "error": {"字段名": ["错误1", ...]}}
"""

import logging

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from app01 import models
from app01.forms import TaskModelForm
from app01.utils.decorators import require_perm
from app01.utils.pagination import Pagination

logger = logging.getLogger("hrms")


@require_perm("task:view")
def task_list(request):
    """任务列表 + 新建表单（表单通过 AJAX 提交）。"""
    queryset = models.Task.objects.select_related("leader", "create_by").order_by("-create_time")

    level = request.GET.get("level", "").strip()
    if level.isdigit():
        queryset = queryset.filter(level=int(level))

    keyword = request.GET.get("q", "").strip()
    if keyword:
        queryset = queryset.filter(title__icontains=keyword)

    page_object = Pagination(request, queryset, page_size=8)
    context = {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(always_show=True),
        "total_count": page_object.total_count,
        "form": TaskModelForm(),
        "level": level,
        "keyword": keyword,
        "level_choices": models.Task.LEVEL_CHOICES,
    }
    return render(request, "task/list.html", context)


@require_perm("task:add")
@require_POST
def task_add_ajax(request):
    """AJAX 提交任务：校验失败时把字段错误原样返回给前端回显。

    为什么用 ``@require_POST``：新增是有副作用的写操作，只允许 POST，
    避免被浏览器预取或爬虫用 GET 触发。

    为什么``JsonResponse``可以直接吃``form.errors``：``ErrorDict`` 本身就是
    ``{"字段名": ["错误文案", ...]}`` 的结构，前端按字段名找到对应输入框，
    把错误写进旁边的 ``.field-error``，从而实现“不刷新页面也能提示”。
    """
    form = TaskModelForm(data=request.POST)
    if form.is_valid():
        record = form.save(commit=False)
        record.create_by = request.user
        record.save()
        logger.info("新增任务 title=%s by=%s", record.title, request.user.username)
        return JsonResponse(
            {
                "status": True,
                "data": {
                    "id": record.id,
                    "title": record.title,
                    "level": record.get_level_display(),
                    "leader": record.leader.name,
                },
            }
        )

    # ErrorDict 是 dict[str, list[str]]，可以直接序列化
    return JsonResponse({"status": False, "error": form.errors}, status=400)


@require_perm("task:add")
@require_POST
def task_toggle_ajax(request):
    """AJAX 切换任务完成状态。

    只更新 ``completed`` 一个字段（``update_fields``），避免整行重写；
    返回最新状态，前端据 ``data.completed`` 决定给标签上色。
    """
    nid = request.POST.get("nid")
    row_object = models.Task.objects.filter(id=nid).first()
    if not row_object:
        return JsonResponse({"status": False, "error": "任务不存在"}, status=404)
    row_object.completed = not row_object.completed
    row_object.save(update_fields=["completed"])
    return JsonResponse({"status": True, "data": {"completed": row_object.completed}})


@require_perm("task:add")
def task_delete(request):
    """删除任务（普通请求，便于直接跳转刷新列表）。"""
    nid = request.GET.get("nid") or request.POST.get("nid")
    models.Task.objects.filter(id=nid).delete()
    return redirect("/task/list/")
