# app01/utils/bootstrap.py
"""Form / ModelForm 的公共基类：统一给字段添加 Bootstrap 3 样式。

沿用 ems 项目中的做法，并做了两点增强：
1. 密码框、复选框、文件框使用与普通输入框不同的样式类；
2. 自动把字段错误信息也挂到 widget 上，模板里 ``{{ field }}`` 即可带红色边框。
"""

from django import forms


def _widget_class(field: forms.BoundField | forms.Field) -> str:
    """按控件类型返回合适的 Bootstrap 样式类。"""
    widget = field.widget
    if isinstance(widget, forms.CheckboxInput):
        return "checkbox"
    if isinstance(widget, forms.FileInput):
        return ""  # 文件框交给模板自定义
    if isinstance(widget, forms.Select):
        return "form-control"
    return "form-control"


def _apply_bootstrap(fields):
    """给所有字段添加样式，placeholder 默认使用字段 label。"""
    for field in fields.values():
        cls = _widget_class(field)
        attrs = dict(field.widget.attrs or {})
        if cls:
            attrs["class"] = cls
        # 文本类控件才设置 placeholder
        if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.EmailInput, forms.Textarea)):
            attrs.setdefault("placeholder", field.label or "")
        field.widget.attrs = attrs


class BootstrapForm(forms.Form):
    """普通 Form 的基类。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self.fields)


class BootstrapModelForm(forms.ModelForm):
    """所有业务 ModelForm 的基类，保证各页面表单风格一致。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self.fields)
        # 给每个输入框加 id，便于前端 AJAX 回显错误时定位
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("id", f"id_{name}")
