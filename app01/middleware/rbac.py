# app01/middleware/rbac.py
"""模块级权限校验中间件（T5 的第一层）。

设计说明：
- 中间件做“模块级”粗粒度校验：只要访问 ``/employee/`` 下的任意地址，
  用户至少要有 ``employee:*`` 中的一项权限；
- 具体接口（新增/编辑/删除）的细粒度校验由视图上的 ``@require_perm`` 装饰器完成；
- 两个层次使用同一套权限编码（app01/utils/permissions.py），不会打架。
"""

import logging

from django.http import JsonResponse
from django.shortcuts import render

from app01.utils.permissions import MODULE_URL_PREFIX

logger = logging.getLogger("hrms.security")


class PermissionMiddleware:
    """按 URL 前缀做模块级权限拦截。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        path = request.path_info

        module = None
        for prefix, name in MODULE_URL_PREFIX.items():
            if path.startswith(prefix):
                module = name
                break

        # 不属于受控模块、未登录（交给 AuthMiddleware）、超管：直接放行
        if module is None or user is None or not user.is_authenticated or user.is_superuser:
            return self.get_response(request)

        codes = user.permission_codes
        if any(code.startswith(f"{module}:") for code in codes):
            return self.get_response(request)

        logger.warning(
            "模块权限拒绝 user=%s path=%s module=%s",
            user.username,
            path,
            module,
        )
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": False, "error": "您没有访问该模块的权限"}, status=403)
        return render(
            request,
            "403.html",
            {"required": f"{module} 模块权限", "status_code": 403},
            status=403,
        )
