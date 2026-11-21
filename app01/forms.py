# app01/forms.py
"""业务表单：所有 ModelForm 校验集中在这里（模型 / 表单 / 视图分层）。

统一约定：
- 继承 ``BootstrapModelForm``，自动获得 Bootstrap 样式；
- ``_post_clean`` 之外的自定义规则写在 ``clean_xxx`` / ``clean`` 中；
- 错误信息使用中文，且挂到具体字段，方便页面 ``{{ field.errors.0 }}`` 展示。

为什么“唯一性”既在表单里查一遍、数据库里又建唯一约束：
- 表单层负责把“该手机号已被使用”这样的中文提示展示给用户，属于用户体验；
- 数据库层负责最终一致性，防止并发提交（两个人同时通过表单校验）或脚本导入；
- 两层各司其职，不能只留其中一层。
"""

import re
from datetime import datetime
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from app01 import models
from app01.utils.bootstrap import BootstrapForm, BootstrapModelForm

MOBILE_REGEX = r"^1[3-9]\d{9}$"


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------
class LoginForm(BootstrapForm):
    """登录表单：用户名 + 密码 + 图片验证码。"""

    username = forms.CharField(
        label="用户名", max_length=32, widget=forms.TextInput(attrs={"autofocus": True})
    )
    password = forms.CharField(label="密码", widget=forms.PasswordInput(render_value=True))
    code = forms.CharField(label="验证码", max_length=8, widget=forms.TextInput(attrs={"autocomplete": "off"}))

    def clean_code(self):
        """只做非空校验，验证码比对在视图中完成（需要 session）。"""
        code = self.cleaned_data.get("code", "").strip()
        if not code:
            raise ValidationError("请输入验证码")
        return code


# ---------------------------------------------------------------------------
# 部门
# ---------------------------------------------------------------------------
class DepartmentModelForm(BootstrapModelForm):
    """部门新增 / 编辑表单。"""

    class Meta:
        model = models.Department
        fields = ["title", "note"]
        labels = {"title": "部门名称", "note": "备注"}
        widgets = {"note": forms.TextInput(attrs={"maxlength": 100})}

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if len(title) < 2:
            raise ValidationError("部门名称至少 2 个字符")
        # 编辑时排除自身
        queryset = models.Department.objects.filter(title=title)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError("该部门已存在")
        return title


# ---------------------------------------------------------------------------
# 员工
# ---------------------------------------------------------------------------
class EmployeeModelForm(BootstrapModelForm):
    """员工新增 / 编辑表单（T3 的核心校验都在这里）。"""

    class Meta:
        model = models.Employee
        fields = ["name", "age", "gender", "mobile", "account", "create_time", "depart", "avatar", "is_active"]
        widgets = {
            "create_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "avatar": forms.FileInput(attrs={"accept": "image/*"}),
            "account": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }
        labels = {
            "create_time": "入职时间",
            "depart": "所属部门",
            "avatar": "头像",
            "is_active": "在职",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["create_time"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        self.fields["depart"].empty_label = "请选择部门"
        self.fields["create_time"].initial = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

    # -- 字段级校验 ------------------------------------------------------
    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not (2 <= len(name) <= 16):
            raise ValidationError("姓名长度需在 2 - 16 个字符之间")
        return name

    def clean_age(self):
        age = self.cleaned_data.get("age")
        if age is None or not (18 <= age <= 65):
            raise ValidationError("年龄需在 18 - 65 岁之间")
        return age

    def clean_mobile(self):
        """手机号格式校验 + 唯一性校验（编辑时排除自身）。

        为什么要 ``exclude(pk=self.instance.pk)``：编辑时表单里填的还是原来那个
        号码，如果不排除自己，会把自己判成“重复”，导致用户不改手机号就保存不了。
        同理，部门名称、角色编码、考勤日期、薪资月份的重复判断都用了这一写法。
        """
        mobile = (self.cleaned_data.get("mobile") or "").strip()
        if not re.match(MOBILE_REGEX, mobile):
            raise ValidationError("手机号格式不正确（应为 1 开头的 11 位数字）")

        queryset = models.Employee.objects.filter(mobile=mobile)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError("该手机号已被使用，请更换")
        return mobile

    def clean_account(self):
        account = self.cleaned_data.get("account")
        if account is not None and account < Decimal("0"):
            raise ValidationError("账户余额不能为负数")
        return account

    def clean_avatar(self):
        """头像：限制格式与大小（2MB）。"""
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size"):
            if avatar.size > 2 * 1024 * 1024:
                raise ValidationError("头像大小不能超过 2MB")
            ext = str(avatar.name).rsplit(".", 1)[-1].lower() if "." in str(avatar.name) else ""
            if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
                raise ValidationError("头像仅支持 jpg / png / gif / webp 格式")
        return avatar


# ---------------------------------------------------------------------------
# 考勤
# ---------------------------------------------------------------------------
class AttendanceModelForm(BootstrapModelForm):
    """考勤表单：状态字段不暴露给用户，由上下班时间自动计算。"""

    class Meta:
        model = models.Attendance
        fields = ["employee", "date", "check_in", "check_out", "remark"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "check_in": forms.TimeInput(attrs={"type": "time"}),
            "check_out": forms.TimeInput(attrs={"type": "time"}),
        }
        labels = {"date": "考勤日期", "check_in": "上班时间", "check_out": "下班时间"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%d"]
        self.fields["check_in"].input_formats = ["%H:%M", "%H:%M:%S"]
        self.fields["check_out"].input_formats = ["%H:%M", "%H:%M:%S"]
        self.fields["employee"].empty_label = "请选择员工"

    def clean_date(self):
        day = self.cleaned_data.get("date")
        if day and day > timezone.localdate():
            raise ValidationError("考勤日期不能晚于今天")
        return day

    def clean(self):
        """表单级（跨字段）校验：下班时间必须晚于上班时间、同人同日不可重复。

        ``clean_xxx`` 只拿得到单个字段，涉及两个字段关系的规则必须写在 ``clean``；
        校验失败时用 ``add_error(字段名, 文案)`` 把错误挂到具体字段上，
        这样模板里 ``{{ form.check_out.errors.0 }}`` 就能显示在对应输入框下方。
        """
        cleaned = super().clean()
        employee = cleaned.get("employee")
        day = cleaned.get("date")
        check_in = cleaned.get("check_in")
        check_out = cleaned.get("check_out")

        if check_in and check_out and check_out <= check_in:
            self.add_error("check_out", "下班时间必须晚于上班时间")

        # 同一员工同一天只能有一条记录（编辑时排除自身）
        if employee and day:
            queryset = models.Attendance.objects.filter(employee=employee, date=day)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                self.add_error("date", "该员工当天已有考勤记录")
        return cleaned


# ---------------------------------------------------------------------------
# 薪资
# ---------------------------------------------------------------------------
class SalaryModelForm(BootstrapModelForm):
    """薪资表单。实发工资不在表单里出现，由 基本工资+奖金-扣款 计算。"""

    class Meta:
        model = models.Salary
        fields = ["employee", "month", "base_salary", "bonus", "deduction", "remark"]
        widgets = {
            "month": forms.TextInput(attrs={"type": "month", "placeholder": "YYYY-MM"}),
            "base_salary": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "bonus": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "deduction": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }
        labels = {"month": "月份", "base_salary": "基本工资", "bonus": "奖金", "deduction": "扣款"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].empty_label = "请选择员工"

    def clean_month(self):
        month = (self.cleaned_data.get("month") or "").strip()
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", month):
            raise ValidationError("月份格式应为 YYYY-MM，例如 2026-11")
        return month

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get("employee")
        month = cleaned.get("month")
        if employee and month:
            queryset = models.Salary.objects.filter(employee=employee, month=month)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                self.add_error("month", "该员工本月薪资已录入")
        return cleaned


# ---------------------------------------------------------------------------
# 公告
# ---------------------------------------------------------------------------
class AnnouncementModelForm(BootstrapModelForm):
    """公告表单。"""

    class Meta:
        model = models.Announcement
        fields = ["title", "content", "is_top"]
        widgets = {"content": forms.Textarea(attrs={"rows": 6})}
        labels = {"is_top": "置顶"}

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if len(title) < 4:
            raise ValidationError("标题至少 4 个字符")
        return title

    def clean_content(self):
        content = (self.cleaned_data.get("content") or "").strip()
        if len(content) < 10:
            raise ValidationError("公告内容至少 10 个字符")
        return content


# ---------------------------------------------------------------------------
# 任务（AJAX）
# ---------------------------------------------------------------------------
class TaskModelForm(BootstrapModelForm):
    """任务表单：AJAX 提交，错误按字段返回 JSON。"""

    class Meta:
        model = models.Task
        fields = ["level", "title", "detail", "leader"]
        widgets = {"detail": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["leader"].empty_label = "请选择负责人"

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if len(title) < 2:
            raise ValidationError("任务标题至少 2 个字符")
        return title

    def clean_detail(self):
        detail = (self.cleaned_data.get("detail") or "").strip()
        if len(detail) < 5:
            raise ValidationError("任务详情至少 5 个字符")
        return detail


# ---------------------------------------------------------------------------
# 系统管理：用户 / 角色
# ---------------------------------------------------------------------------
class UserCreateForm(BootstrapModelForm):
    """新建用户：用户名 + 密码 + 角色 + 可选部门/员工档案关联。"""

    password = forms.CharField(label="密码", min_length=6, widget=forms.PasswordInput(render_value=True))
    confirm_password = forms.CharField(label="确认密码", widget=forms.PasswordInput(render_value=True))

    class Meta:
        model = models.User
        fields = ["username", "real_name", "phone", "department", "employee", "roles", "is_active"]
        widgets = {"roles": forms.CheckboxSelectMultiple()}
        labels = {
            "username": "用户名",
            "real_name": "姓名",
            "phone": "手机号",
            "department": "所属部门",
            "employee": "关联员工档案",
            "roles": "角色",
            "is_active": "启用",
        }
        help_texts = {"employee": "普通员工账号需关联档案，才能查看“我的考勤/薪资”"}

    field_order = ["username", "real_name", "phone", "password", "confirm_password", "department", "employee", "roles", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].empty_label = "（可选）所属部门"
        self.fields["employee"].empty_label = "（可选）关联员工"
        self.fields["roles"].widget.attrs.pop("class", None)

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if models.User.objects.filter(username=username).exists():
            raise ValidationError("该用户名已存在")
        return username

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not re.match(MOBILE_REGEX, phone):
            raise ValidationError("手机号格式不正确")
        return phone

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "两次输入的密码不一致")
        if not cleaned.get("roles"):
            self.add_error("roles", "请至少选择一个角色")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        # 使用 Django 内置哈希（PBKDF2），严禁明文存储
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserUpdateForm(BootstrapModelForm):
    """编辑用户（不在此处改密码，改密走“重置密码”）。"""

    class Meta:
        model = models.User
        fields = ["username", "real_name", "phone", "department", "employee", "roles", "is_active"]
        widgets = {"roles": forms.CheckboxSelectMultiple()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].empty_label = "（可选）所属部门"
        self.fields["employee"].empty_label = "（可选）关联员工"
        self.fields["roles"].widget.attrs.pop("class", None)

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if models.User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError("该用户名已存在")
        return username


class ResetPasswordForm(BootstrapForm):
    """重置密码：新密码 + 确认密码。"""

    password = forms.CharField(label="新密码", min_length=6, widget=forms.PasswordInput(render_value=True))
    confirm_password = forms.CharField(label="确认密码", widget=forms.PasswordInput(render_value=True))

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "两次输入的密码不一致")
        return cleaned


class RoleModelForm(BootstrapModelForm):
    """角色表单：角色信息 + 权限多选（CheckboxSelectMultiple）。"""

    class Meta:
        model = models.Role
        fields = ["name", "code", "description", "permissions"]
        widgets = {"permissions": forms.CheckboxSelectMultiple()}
        labels = {"permissions": "权限"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 复选框不应套用 form-control
        self.fields["permissions"].widget.attrs.pop("class", None)

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if not re.match(r"^[a-z][a-z0-9_]{1,31}$", code):
            raise ValidationError("角色编码需为小写字母/数字/下划线，且以字母开头")
        queryset = models.Role.objects.filter(code=code)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError("角色编码已存在")
        return code
