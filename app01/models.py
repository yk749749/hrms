"""企业员工管理系统（HRMS）数据模型。

模块划分：
- RBAC：Permission（权限）- Role（角色）- User（自定义用户，继承 AbstractUser）
- 组织：Department（部门）- Employee（员工）
- 业务：Attendance（考勤）- Salary（薪资）- Announcement（公告）- Task（任务）

约定：
- 所有金额字段使用 DecimalField(10, 2)，避免浮点误差。
- 需要“自动计算”的字段（考勤状态、实发工资）统一在模型 save() 中兜底计算，
  视图层再用 commit=False 计算一次，保证前后端数据一致（见任务书阶段四提示）。
"""

from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


# ---------------------------------------------------------------------------
# 一、RBAC：权限 / 角色 / 用户
# ---------------------------------------------------------------------------
class Permission(models.Model):
    """权限项（菜单 + 按钮 + 接口）。

    权限以 ``模块:动作`` 形式编码，例如 ``employee:add``、``salary:edit``，
    视图装饰器、中间件与模板标签都以此 code 为准。
    """

    name = models.CharField("权限名称", max_length=64)
    code = models.CharField("权限编码", max_length=64, unique=True)
    module = models.CharField("所属模块", max_length=32, blank=True, default="")
    description = models.CharField("说明", max_length=200, blank=True, default="")
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "hrms_permission"
        verbose_name = "权限"
        verbose_name_plural = verbose_name
        ordering = ["module", "code"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Role(models.Model):
    """角色（用户 - 角色 - 权限 三层模型的中间层）。"""

    name = models.CharField("角色名称", max_length=32, unique=True)
    code = models.CharField("角色编码", max_length=32, unique=True)
    permissions = models.ManyToManyField(
        Permission, verbose_name="拥有权限", blank=True, related_name="roles"
    )
    description = models.CharField("说明", max_length=200, blank=True, default="")
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "hrms_role"
        verbose_name = "角色"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    """自定义用户模型（继承 AbstractUser，使用 Django 内置哈希存密码）。

    - ``roles``：用户拥有的角色，角色再关联权限，构成 RBAC 三层结构。
    - ``department``：部门管理员的数据范围（只看/只管本部门）。
    - ``employee``：普通员工账号与员工档案的一对一映射，用于“查看我的档案/考勤/薪资”。
    """

    real_name = models.CharField("姓名", max_length=32, blank=True, default="")
    phone = models.CharField(
        "手机号",
        max_length=11,
        blank=True,
        default="",
        validators=[RegexValidator(r"^1[3-9]\d{9}$", "手机号格式不正确")],
    )
    roles = models.ManyToManyField(Role, verbose_name="角色", blank=True, related_name="users")
    department = models.ForeignKey(
        "Department",
        verbose_name="所属部门",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
        help_text="部门管理员的数据范围，普通员工可留空",
    )
    employee = models.OneToOneField(
        "Employee",
        verbose_name="关联员工档案",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="login_account",
    )
    create_time = models.DateTimeField("创建时间", auto_now_add=True, null=True)

    class Meta:
        db_table = "hrms_user"
        verbose_name = "用户"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return self.real_name or self.username

    # -- 便于权限体系使用的便捷方法 -------------------------------------
    @property
    def permission_codes(self) -> set[str]:
        """当前用户拥有的全部权限编码（超管视为拥有全部）。"""
        if self.is_superuser:
            return set(
                Permission.objects.values_list("code", flat=True)
            ) | {"*"}
        return set(
            Permission.objects.filter(roles__users__id=self.pk)
            .values_list("code", flat=True)
            .distinct()
        )

    def has_perm_code(self, code: str) -> bool:
        """判断是否具备某个权限编码。超管直接放行。"""
        if self.is_superuser:
            return True
        return code in self.permission_codes

    @property
    def role_names(self) -> str:
        return "、".join(self.roles.values_list("name", flat=True)) or "未分配角色"


# ---------------------------------------------------------------------------
# 二、组织：部门 / 员工
# ---------------------------------------------------------------------------
class Department(models.Model):
    """部门表。员工外键使用 PROTECT，删除有员工的部门时给出友好提示而不是丢数据。"""

    title = models.CharField("部门名称", max_length=32, unique=True)
    note = models.CharField("备注", max_length=100, blank=True, default="")
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "hrms_department"
        verbose_name = "部门"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self) -> str:
        return self.title


class Employee(models.Model):
    """员工表（T3）。

    校验规则见 ``app01/forms.py``：姓名长度、年龄范围、手机号正则且唯一。

    设计说明（答辩常问）：
    - ``mobile`` 加 ``unique=True``：手机号是员工的自然唯一标识，数据库层再加一道
      约束，即使绕过表单（如后台、脚本）也不会写进重复号码；
    - ``depart`` 用 ``on_delete=PROTECT`` 而不是 CASCADE：删除部门属于组织调整，
      误删会连带丢失员工档案，因此宁可报错让操作者先处理员工；
    - ``Meta.indexes`` 建 ``(depart, name)`` 联合索引：列表页最常见的查询就是
      “某部门下的员工”，联合索引可以命中该组合条件。
    """

    GENDER_CHOICES = ((1, "男"), (2, "女"))

    name = models.CharField("姓名", max_length=16)
    age = models.IntegerField(
        "年龄",
        validators=[
            MinValueValidator(18, message="年龄需在 18 - 65 岁之间"),
            MaxValueValidator(65, message="年龄需在 18 - 65 岁之间"),
        ],
        help_text="18 - 65 岁",
    )
    gender = models.SmallIntegerField("性别", choices=GENDER_CHOICES, default=1)
    mobile = models.CharField(
        "手机号",
        max_length=11,
        unique=True,
        validators=[RegexValidator(r"^1[3-9]\d{9}$", "手机号格式不正确")],
    )
    account = models.DecimalField("账户余额", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    create_time = models.DateTimeField("入职时间")
    depart = models.ForeignKey(
        Department,
        verbose_name="所属部门",
        on_delete=models.PROTECT,
        related_name="employees",
    )
    avatar = models.ImageField("头像", upload_to="avatar/", blank=True, null=True)
    is_active = models.BooleanField("在职", default=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "hrms_employee"
        verbose_name = "员工"
        verbose_name_plural = verbose_name
        ordering = ["id"]
        indexes = [models.Index(fields=["depart", "name"])]

    def __str__(self) -> str:
        return self.name

    @property
    def gender_display(self) -> str:
        return self.get_gender_display()


# ---------------------------------------------------------------------------
# 三、业务：考勤 / 薪资 / 公告 / 任务
# ---------------------------------------------------------------------------
class Attendance(models.Model):
    """考勤表（T6）。状态由上下班时间自动计算，不允许手工选择。"""

    STATUS_ON_TIME = 1
    STATUS_LATE = 2
    STATUS_EARLY = 3
    STATUS_ABSENT = 4
    STATUS_LATE_EARLY = 5
    STATUS_CHOICES = (
        (STATUS_ON_TIME, "按时"),
        (STATUS_LATE, "迟到"),
        (STATUS_EARLY, "早退"),
        (STATUS_ABSENT, "缺勤"),
        (STATUS_LATE_EARLY, "迟到并早退"),
    )

    # 公司标准上下班时间，状态判断依据
    WORK_START = "09:00"
    WORK_END = "18:00"

    employee = models.ForeignKey(
        Employee, verbose_name="员工", on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField("考勤日期")
    check_in = models.TimeField("上班时间", null=True, blank=True)
    check_out = models.TimeField("下班时间", null=True, blank=True)
    status = models.SmallIntegerField("考勤状态", choices=STATUS_CHOICES, default=STATUS_ON_TIME)
    remark = models.CharField("备注", max_length=200, blank=True, default="")
    create_time = models.DateTimeField("记录时间", auto_now_add=True)

    class Meta:
        db_table = "hrms_attendance"
        verbose_name = "考勤"
        verbose_name_plural = verbose_name
        ordering = ["-date", "-id"]
        # 同一员工同一天只允许一条考勤记录。
        # 业务上表单已经校验过，这里再用数据库唯一约束兜底，防止并发提交或脚本导入产生重复。
        constraints = [
            models.UniqueConstraint(fields=["employee", "date"], name="uniq_attendance_employee_date")
        ]
        indexes = [models.Index(fields=["date", "employee"])]

    def __str__(self) -> str:
        return f"{self.employee} {self.date} {self.get_status_display()}"

    def compute_status(self) -> int:
        """根据上下班时间计算考勤状态。

        规则（对应任务书 T6）：
        - 两次打卡都没有 -> 缺勤
        - 迟于 09:00 上班 -> 迟到
        - 早于 18:00 下班 -> 早退
        - 同时迟到 + 早退 -> 迟到并早退
        - 其余 -> 按时

        为什么单独抽成一个方法：视图层用 ``form.save(commit=False)`` 时可以先调它
        做展示，``save()`` 里再调一次兜底，保证“页面显示的状态”和“库里的状态”一致。
        """
        from datetime import time

        work_start = time.fromisoformat(self.WORK_START)
        work_end = time.fromisoformat(self.WORK_END)

        if self.check_in is None and self.check_out is None:
            return self.STATUS_ABSENT

        late = self.check_in is not None and self.check_in > work_start
        early = self.check_out is not None and self.check_out < work_end
        # 只打了一次卡（另一次缺失）按缺勤处理，避免“漏打卡”被算成按时
        if self.check_in is None or self.check_out is None:
            return self.STATUS_ABSENT
        if late and early:
            return self.STATUS_LATE_EARLY
        if late:
            return self.STATUS_LATE
        if early:
            return self.STATUS_EARLY
        return self.STATUS_ON_TIME

    def save(self, *args, **kwargs):
        """保存前自动刷新状态，保证数据库里不会出现与时间矛盾的 status。

        这是“模型层兜底”：不管从表单、管理后台还是脚本写入，状态都会被重算，
        避免有人手工改 check_in 却忘了改 status。
        """
        self.status = self.compute_status()
        super().save(*args, **kwargs)


class Salary(models.Model):
    """薪资表（T7）。实发工资 = 基本工资 + 奖金 - 扣款。

    设计说明（答辩常问）：
    - ``month`` 用 ``CharField("YYYY-MM")`` 而不是 ``DateField``：薪资是按“自然月”
      统计的，用字符串可以直接按月份排序、按月份做下拉筛选，也避免“每月该取哪一天”
      这种无意义的歧义；正则校验保证格式统一。
    - ``total`` 作为冗余字段落库：虽然可以由前三个字段算出来，但列表页需要
      Sum/Avg/Max 统计，若每次都在 SQL 里做表达式聚合，写法复杂且无法直接建索引；
      落库后统计只需 ``Sum("total")``，代价是写入时必须保证计算一致——所以计算
      统一放在 ``save()`` 里，任何入口（表单、脚本、后台）都走同一套逻辑。
    """

    employee = models.ForeignKey(
        Employee, verbose_name="员工", on_delete=models.CASCADE, related_name="salaries"
    )
    month = models.CharField(
        "月份",
        max_length=7,
        help_text="格式 YYYY-MM，例如 2026-11",
        validators=[RegexValidator(r"^\d{4}-(0[1-9]|1[0-2])$", "月份格式应为 YYYY-MM")],
    )
    base_salary = models.DecimalField("基本工资", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    bonus = models.DecimalField("奖金", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    deduction = models.DecimalField("扣款", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField("实发工资", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    remark = models.CharField("备注", max_length=200, blank=True, default="")
    create_time = models.DateTimeField("录入时间", auto_now_add=True)

    class Meta:
        db_table = "hrms_salary"
        verbose_name = "薪资"
        verbose_name_plural = verbose_name
        ordering = ["-month", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "month"], name="uniq_salary_employee_month")
        ]
        indexes = [models.Index(fields=["month", "employee"])]

    def __str__(self) -> str:
        return f"{self.employee} {self.month} {self.total}"

    def compute_total(self) -> Decimal:
        """实发 = 基本工资 + 奖金 - 扣款。"""
        base = self.base_salary or Decimal("0.00")
        bonus = self.bonus or Decimal("0.00")
        deduction = self.deduction or Decimal("0.00")
        return base + bonus - deduction

    def save(self, *args, **kwargs):
        self.total = self.compute_total()
        super().save(*args, **kwargs)


class Announcement(models.Model):
    """公告表（T8）。发布时间使用 auto_now_add 自动写入。"""

    title = models.CharField("标题", max_length=64)
    content = models.TextField("内容")
    publisher = models.ForeignKey(
        User,
        verbose_name="发布人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    create_time = models.DateTimeField("发布时间", auto_now_add=True)
    is_top = models.BooleanField("是否置顶", default=False)

    class Meta:
        db_table = "hrms_announcement"
        verbose_name = "公告"
        verbose_name_plural = verbose_name
        # 置顶优先，再按发布时间倒序
        ordering = ["-is_top", "-create_time"]

    def __str__(self) -> str:
        return self.title


class Task(models.Model):
    """任务表（T9）。通过 AJAX 异步提交，后端返回 JSON。"""

    LEVEL_CHOICES = ((1, "紧急"), (2, "重要"), (3, "普通"))

    level = models.SmallIntegerField("级别", choices=LEVEL_CHOICES, default=3)
    title = models.CharField("标题", max_length=64)
    detail = models.TextField("详细信息")
    leader = models.ForeignKey(
        Employee, verbose_name="负责人", on_delete=models.CASCADE, related_name="tasks"
    )
    completed = models.BooleanField("已完成", default=False)
    create_by = models.ForeignKey(
        User, verbose_name="创建人", on_delete=models.SET_NULL, null=True, blank=True
    )
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "hrms_task"
        verbose_name = "任务"
        verbose_name_plural = verbose_name
        ordering = ["level", "-create_time"]

    def __str__(self) -> str:
        return self.title


# ---------------------------------------------------------------------------
# 四、AI 智能助手：制度知识库（T3）
# ---------------------------------------------------------------------------
class Knowledge(models.Model):
    """企业知识库条目（制度 / 手册），供“制度问答”检索后注入提示词。

    设计说明（答辩常问）：
    - 只存“标题 + 内容”就能跑通简化版 RAG：检索用 ``icontains`` 关键词匹配，
      命中后拼成 ``【资料】`` 段落塞进提示词，模型照着资料回答；
    - ``category`` 只是给人看的分组（考勤 / 报销 / 请假……），检索不依赖它，
      没有分类也能用，所以允许留空；
    - 不做全文索引：数据量在几十条量级，``LIKE`` 足够快，加索引反而增加维护成本。
    """

    title = models.CharField("标题", max_length=128)
    category = models.CharField("分类", max_length=32, blank=True, default="")
    content = models.TextField("内容")
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "hrms_knowledge"
        verbose_name = "制度知识"
        verbose_name_plural = verbose_name
        ordering = ["category", "id"]

    def __str__(self) -> str:
        return self.title

