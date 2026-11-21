# app01/views/system.py
"""系统管理：用户 / 角色 / 权限（RBAC 的后台维护界面）。"""

import logging

from django.shortcuts import redirect, render

from app01 import models
from app01.forms import ResetPasswordForm, RoleModelForm, UserCreateForm, UserUpdateForm
from app01.utils.decorators import require_perm
from app01.utils.pagination import Pagination

logger = logging.getLogger("hrms")


# ---------------------------------------------------------------------------
# 用户
# ---------------------------------------------------------------------------
@require_perm("system:view")
def user_list(request):
    """用户列表：搜索 + 分页；预取角色避免 N+1。"""
    queryset = models.User.objects.select_related("department", "employee").prefetch_related("roles").order_by("id")

    keyword = request.GET.get("q", "").strip()
    if keyword:
        queryset = queryset.filter(username__icontains=keyword)

    page_object = Pagination(request, queryset, page_size=10)
    context = {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(always_show=True),
        "total_count": page_object.total_count,
        "keyword": keyword,
    }
    return render(request, "system/user_list.html", context)


@require_perm("system:manage")
def user_add(request):
    """新建用户（密码使用 set_password 存哈希）。"""
    if request.method == "GET":
        return render(request, "system/user_change.html", {"form": UserCreateForm(), "title": "新建用户"})

    form = UserCreateForm(data=request.POST)
    if form.is_valid():
        user = form.save()
        logger.info("新建用户 username=%s roles=%s by=%s", user.username, user.role_names, request.user.username)
        return redirect("/system/user/list/")
    return render(request, "system/user_change.html", {"form": form, "title": "新建用户"})


@require_perm("system:manage")
def user_edit(request, nid):
    """编辑用户（含角色调整）。"""
    row_object = models.User.objects.filter(id=nid).first()
    if not row_object:
        return redirect("/system/user/list/")

    if request.method == "GET":
        return render(
            request,
            "system/user_change.html",
            {"form": UserUpdateForm(instance=row_object), "title": "编辑用户", "row_object": row_object},
        )

    form = UserUpdateForm(data=request.POST, instance=row_object)
    if form.is_valid():
        form.save()
        return redirect("/system/user/list/")
    return render(
        request,
        "system/user_change.html",
        {"form": form, "title": "编辑用户", "row_object": row_object},
    )


@require_perm("system:manage")
def user_reset_password(request, nid):
    """重置用户密码。"""
    row_object = models.User.objects.filter(id=nid).first()
    if not row_object:
        return redirect("/system/user/list/")

    if request.method == "GET":
        return render(
            request,
            "system/reset_password.html",
            {"form": ResetPasswordForm(), "title": f"重置密码 - {row_object.username}", "row_object": row_object},
        )

    form = ResetPasswordForm(data=request.POST)
    if form.is_valid():
        row_object.set_password(form.cleaned_data["password"])
        row_object.save(update_fields=["password"])
        logger.info("重置密码 username=%s by=%s", row_object.username, request.user.username)
        return redirect("/system/user/list/")
    return render(
        request,
        "system/reset_password.html",
        {"form": form, "title": f"重置密码 - {row_object.username}", "row_object": row_object},
    )


@require_perm("system:manage")
def user_delete(request):
    """删除用户。"""
    nid = request.GET.get("nid") or request.POST.get("nid")
    models.User.objects.filter(id=nid).delete()
    return redirect("/system/user/list/")


# ---------------------------------------------------------------------------
# 角色
# ---------------------------------------------------------------------------
@require_perm("system:view")
def role_list(request):
    """角色列表，显示每个角色拥有的权限数量。"""
    queryset = models.Role.objects.prefetch_related("permissions").order_by("id")
    page_object = Pagination(request, queryset, page_size=10)
    return render(
        request,
        "system/role_list.html",
        {
            "queryset": page_object.page_queryset,
            "page_string": page_object.html(always_show=True),
            "total_count": page_object.total_count,
        },
    )


@require_perm("system:manage")
def role_add(request):
    """新建角色。"""
    if request.method == "GET":
        return render(request, "system/role_change.html", {"form": RoleModelForm(), "title": "新建角色"})

    form = RoleModelForm(data=request.POST)
    if form.is_valid():
        form.save()
        return redirect("/system/role/list/")
    return render(request, "system/role_change.html", {"form": form, "title": "新建角色"})


@require_perm("system:manage")
def role_edit(request, nid):
    """编辑角色与权限。"""
    row_object = models.Role.objects.filter(id=nid).first()
    if not row_object:
        return redirect("/system/role/list/")

    if request.method == "GET":
        return render(
            request,
            "system/role_change.html",
            {"form": RoleModelForm(instance=row_object), "title": "编辑角色", "row_object": row_object},
        )

    form = RoleModelForm(data=request.POST, instance=row_object)
    if form.is_valid():
        form.save()
        return redirect("/system/role/list/")
    return render(
        request,
        "system/role_change.html",
        {"form": form, "title": "编辑角色", "row_object": row_object},
    )


@require_perm("system:manage")
def role_delete(request):
    """删除角色。"""
    nid = request.GET.get("nid") or request.POST.get("nid")
    models.Role.objects.filter(id=nid).delete()
    return redirect("/system/role/list/")


@require_perm("system:view")
def permission_list(request):
    """权限清单（只读展示，权限由 init_data 统一维护）。"""
    queryset = models.Permission.objects.order_by("module", "code")
    return render(request, "system/permission_list.html", {"queryset": queryset})
