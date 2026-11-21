# app01/views/announcement.py
"""公告管理（T8）：发布、列表、置顶、搜索、分页。"""

import logging

from django.db.models import Q
from django.shortcuts import redirect, render

from app01 import models
from app01.forms import AnnouncementModelForm
from app01.utils.decorators import require_perm
from app01.utils.pagination import Pagination

logger = logging.getLogger("hrms")


@require_perm("announcement:view")
def announcement_list(request):
    """公告列表：置顶优先 + 标题/内容模糊搜索 + 分页。"""
    queryset = models.Announcement.objects.select_related("publisher")

    keyword = request.GET.get("q", "").strip()
    if keyword:
        queryset = queryset.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))

    page_object = Pagination(request, queryset, page_size=8)
    context = {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(always_show=True),
        "total_count": page_object.total_count,
        "keyword": keyword,
    }
    return render(request, "announcement/list.html", context)


@require_perm("announcement:view")
def announcement_detail(request, nid):
    """公告详情。"""
    row_object = models.Announcement.objects.select_related("publisher").filter(id=nid).first()
    if not row_object:
        return redirect("/announcement/list/")
    return render(request, "announcement/detail.html", {"row_object": row_object})


@require_perm("announcement:add")
def announcement_add(request):
    """发布公告：发布人取当前登录用户，发布时间 auto_now_add 自动写入。"""
    if request.method == "GET":
        return render(
            request, "announcement/change.html", {"form": AnnouncementModelForm(), "title": "发布公告"}
        )

    form = AnnouncementModelForm(data=request.POST)
    if form.is_valid():
        record = form.save(commit=False)
        record.publisher = request.user
        record.save()
        logger.info("发布公告 title=%s by=%s", record.title, request.user.username)
        return redirect("/announcement/list/")
    return render(request, "announcement/change.html", {"form": form, "title": "发布公告"})


@require_perm("announcement:edit")
def announcement_edit(request, nid):
    """编辑公告。"""
    row_object = models.Announcement.objects.filter(id=nid).first()
    if not row_object:
        return redirect("/announcement/list/")

    if request.method == "GET":
        return render(
            request,
            "announcement/change.html",
            {"form": AnnouncementModelForm(instance=row_object), "title": "编辑公告", "row_object": row_object},
        )

    form = AnnouncementModelForm(data=request.POST, instance=row_object)
    if form.is_valid():
        form.save()
        return redirect("/announcement/list/")
    return render(
        request,
        "announcement/change.html",
        {"form": form, "title": "编辑公告", "row_object": row_object},
    )


@require_perm("announcement:edit")
def announcement_toggle_top(request):
    """切换置顶状态。"""
    nid = request.GET.get("nid") or request.POST.get("nid")
    row_object = models.Announcement.objects.filter(id=nid).first()
    if row_object:
        row_object.is_top = not row_object.is_top
        row_object.save(update_fields=["is_top"])
    return redirect("/announcement/list/")


@require_perm("announcement:delete")
def announcement_delete(request):
    """删除公告。"""
    nid = request.GET.get("nid") or request.POST.get("nid")
    models.Announcement.objects.filter(id=nid).delete()
    return redirect("/announcement/list/")
