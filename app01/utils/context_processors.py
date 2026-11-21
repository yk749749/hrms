# app01/utils/context_processors.py
"""模板上下文：把当前用户的权限编码集合暴露给模板，用于“按权限隐藏按钮”。"""

from app01.utils.permissions import PERMISSION_CODES


def permission_codes(request):
    """返回 ``perms_codes``（set）与 ``current_user``，模板中可直接使用。"""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"perms_codes": set(), "current_user": None}

    if user.is_superuser:
        codes = set(PERMISSION_CODES) | {"*"}
    else:
        codes = user.permission_codes
    return {"perms_codes": codes, "current_user": user}
