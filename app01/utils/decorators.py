# app01/utils/decorators.py
"""接口级权限校验装饰器与 AJAX 判断工具（T5）。

中间件负责“没登录就拦”，这里负责“登录了但没有权限也要拦”：
- 普通请求：直接返回 403 页面；
- AJAX 请求：返回 JSON ``{"status": false, "error": "..."}``，前端可回显。
"""

import logging
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger("hrms.security")


def is_ajax(request) -> bool:
    """判断请求是否来自 AJAX（兼容不同前端框架的标记头）。"""
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.headers.get("accept") == "application/json"
    )


def require_perm(*codes, mode="any"):
    """要求当前用户具备指定权限编码之一（``mode="any"``）或全部（``mode="all"``）。

    用法::

        @require_perm("employee:add")
        def employee_add(request): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            # 未登录：交给登录页（中间件一般已拦截，这里做兜底）
            if user is None or not user.is_authenticated:
                if is_ajax(request):
                    return JsonResponse({"status": False, "error": "登录状态已失效"}, status=401)
                return redirect(f"{reverse('login')}?next={request.path}")

            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            allowed = (
                all(user.has_perm_code(c) for c in codes)
                if mode == "all"
                else any(user.has_perm_code(c) for c in codes)
            )
            if allowed:
                return view_func(request, *args, **kwargs)

            logger.warning(
                "权限拒绝 user=%s roles=%s path=%s required=%s",
                user.username,
                user.role_names,
                request.path,
                ",".join(codes),
            )
            if is_ajax(request):
                return JsonResponse({"status": False, "error": "您没有该操作的权限"}, status=403)

            # 非 AJAX：渲染 403 页面
            from django.shortcuts import render

            return render(
                request,
                "403.html",
                {"required": "、".join(codes), "status_code": 403},
                status=403,
            )

        return wrapper

    return decorator
