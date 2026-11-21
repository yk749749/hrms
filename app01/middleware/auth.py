# app01/middleware/auth.py
"""登录校验中间件（T4）。

未登录访问任何业务页面时统一跳转到登录页，并带上 ``next`` 参数，
登录成功后可回到原页面。
"""

from django.shortcuts import redirect
from django.urls import reverse

# 白名单：登录相关、验证码、后台登录、静态/媒体资源
ALLOW_WITHOUT_LOGIN = (
    "/login/",
    "/logout/",
    "/image/code/",
    "/static/",
    "/media/",
    "/favicon.ico",
)


class AuthMiddleware:
    """未登录时统一跳转到登录页面。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path.startswith(ALLOW_WITHOUT_LOGIN) or path == "/":
            # 根路径由首页视图自行判断（未登录渲染登录引导）
            if path == "/" and request.user.is_authenticated:
                return self.get_response(request)
            if path.startswith(ALLOW_WITHOUT_LOGIN):
                return self.get_response(request)

        if request.user.is_authenticated:
            return self.get_response(request)

        # 未登录：AJAX 返回 JSON，普通请求跳登录页
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            from django.http import JsonResponse

            return JsonResponse({"status": False, "error": "登录状态已失效"}, status=401)

        login_url = reverse("login")
        return redirect(f"{login_url}?next={path}")
