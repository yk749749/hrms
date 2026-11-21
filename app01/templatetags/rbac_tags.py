# app01/templatetags/rbac_tags.py
"""模板过滤器：按权限隐藏按钮、格式化金额与状态徽章。"""

from django import template

register = template.Library()


@register.filter(name="has_perm")
def has_perm(user, code):
    """``{% if current_user|has_perm:'employee:add' %}`` 形式的按钮级权限判断。"""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if code == "*":
        return user.is_superuser
    return user.has_perm_code(code)


@register.filter(name="money")
def money(value):
    """金额格式化：1234.5 -> 1,234.50。"""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


@register.filter(name="status_class")
def status_class(status):
    """把考勤状态映射为 Bootstrap 标签颜色。"""
    mapping = {1: "success", 2: "warning", 3: "info", 4: "danger", 5: "danger"}
    return mapping.get(status, "default")


@register.filter(name="level_class")
def level_class(level):
    """任务级别 -> 标签颜色。"""
    return {1: "danger", 2: "warning", 3: "default"}.get(level, "default")


@register.filter(name="percent")
def percent(value, total):
    """占比（用于首页进度条）。"""
    try:
        total = float(total)
        if total <= 0:
            return 0
        return round(float(value) / total * 100, 1)
    except (TypeError, ValueError):
        return 0
