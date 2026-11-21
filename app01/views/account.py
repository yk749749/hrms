# app01/views/account.py
"""登录 / 注销 / 图片验证码（T4）。"""

import logging
from io import BytesIO
from urllib.parse import urlparse

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from app01.forms import LoginForm
from app01.utils.code import check_code

logger = logging.getLogger("hrms.security")


def _safe_next(request, default="/"):
    """只允许站内跳转，防止登录后被「开放重定向」带到外站。"""
    nxt = request.GET.get("next") or request.POST.get("next") or ""
    if not nxt:
        return default
    parsed = urlparse(nxt)
    if parsed.netloc or parsed.scheme:
        return default
    if not nxt.startswith("/"):
        return default
    return nxt


def login(request):
    """登录：表单校验 + 图片验证码 + Django 哈希密码校验。"""
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "GET":
        return redirect("/login/") if request.path != "/login/" else render(request, "login.html", {"form": LoginForm()})

    form = LoginForm(data=request.POST)
    if not form.is_valid():
        return render(request, "login.html", {"form": form})

    # 1. 图片验证码（不区分大小写）
    session_code = request.session.get("image_code", "")
    input_code = form.cleaned_data["code"]
    if not session_code or input_code.upper() != session_code.upper():
        form.add_error("code", "验证码错误")
        return render(request, "login.html", {"form": form})

    username = form.cleaned_data["username"]
    password = form.cleaned_data["password"]

    # 2. 用户名 / 密码（authenticate 内部使用 Django 哈希比对）
    user = authenticate(request, username=username, password=password)
    if user is None:
        logger.warning("登录失败 username=%s ip=%s", username, request.META.get("REMOTE_ADDR"))
        form.add_error(None, "用户名或密码错误")
        return render(request, "login.html", {"form": form})

    if not user.is_active:
        logger.warning("登录被拒（账号已禁用） username=%s", username)
        form.add_error(None, "该账号已被禁用，请联系管理员")
        return render(request, "login.html", {"form": form})

    # 3. 登录成功：清除验证码，写入会话
    request.session.pop("image_code", None)
    auth_login(request, user)
    logger.info("登录成功 username=%s ip=%s", username, request.META.get("REMOTE_ADDR"))
    return redirect(_safe_next(request))


def image_code(request):
    """生成图片验证码，并把验证码字符串写入 session。"""
    img, code_string = check_code()
    request.session["image_code"] = code_string

    stream = BytesIO()
    img.save(stream, format="PNG")
    response = HttpResponse(stream.getvalue(), content_type="image/png")
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


def logout(request):
    """注销并清空会话。"""
    if request.user.is_authenticated:
        logger.info("注销 username=%s", request.user.username)
    auth_logout(request)
    request.session.clear()
    return redirect(reverse("login"))
