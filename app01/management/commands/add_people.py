"""演示数据补充命令：批量新增员工，并可按需生成考勤与薪资。

用法::

    python manage.py add_people                 # 默认新增 40 人，并生成 15 个工作日考勤 + 3 个月薪资
    python manage.py add_people --count 20      # 只新增 20 人
    python manage.py add_people --people-only   # 只加员工，不生成考勤/薪资
    python manage.py add_people --days 0 --months 0   # 同上

说明：
- 手机号在 ``13900000001`` 起顺序分配，自动跳过已占用的号码；
- 数据用固定随机种子生成，重复执行结果可预期（每人仍会拿到新的手机号）；
- 不修改已有员工、部门与账号，可安全地多次执行。
"""

import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from app01 import models

SURNAMES = [
    "王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
    "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "罗",
    "郑", "梁", "谢", "宋", "唐", "许", "韩", "冯", "邓", "曹",
    "彭", "曾", "肖", "田", "董", "袁", "潘", "蒋", "蔡", "余",
]

GIVEN_MALE = [
    "伟", "强", "磊", "军", "洋", "勇", "杰", "涛", "明", "超",
    "鹏", "宇", "浩", "凯", "斌", "鑫", "晨", "睿", "航", "哲",
    "俊杰", "子豪", "志强", "建国", "文博", "嘉豪", "一鸣", "思远",
]

GIVEN_FEMALE = [
    "芳", "娜", "敏", "静", "丽", "娟", "艳", "霞", "婷", "雪",
    "颖", "琳", "悦", "欣", "怡", "晴", "佳", "瑶", "蕾", "薇",
    "雨欣", "梦琪", "思琪", "晓燕", "文静", "佳怡", "书瑶", "雅琴",
]

NOTES = [
    "应届校招入职", "社招骨干", "内部转岗", "项目组借调", "返聘", "",
]

BASE_BY_DEPARTMENT = {
    "技术部": (9000, 16000),
    "市场部": (6500, 11000),
    "人事部": (6000, 9000),
    "财务部": (7000, 10000),
}
DEFAULT_BASE = (6000, 11000)


class Command(BaseCommand):
    help = "批量新增演示员工数据，可同时生成考勤与薪资"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=40, help="新增员工数量，默认 40")
        parser.add_argument("--days", type=int, default=15, help="为每位新员工生成最近多少个工作日的考勤，默认 15")
        parser.add_argument("--months", type=int, default=3, help="为每位新员工生成最近几个月的薪资，默认 3")
        parser.add_argument("--people-only", action="store_true", help="只新增员工，不生成考勤与薪资")

    def handle(self, *args, **options):
        count = max(0, options["count"])
        if count == 0:
            self.stdout.write(self.style.WARNING("未指定有效的新增数量，未做任何修改"))
            return

        rng = random.Random(20261107)
        departments = list(models.Department.objects.all())
        if not departments:
            self.stderr.write(self.style.ERROR("还没有部门，请先执行 init_data 或 demo_data"))
            return

        existing_mobiles = set(models.Employee.objects.values_list("mobile", flat=True))
        used_names = set(models.Employee.objects.values_list("name", flat=True))

        new_employees = []
        with transaction.atomic():
            for index in range(count):
                gender = 2 if index % 3 == 1 else 1
                department = departments[index % len(departments)]

                name = self._make_name(rng, gender, used_names)
                used_names.add(name)

                mobile = self._next_mobile(existing_mobiles)
                existing_mobiles.add(mobile)

                age = rng.randint(22, 55)
                account = Decimal(rng.randint(0, 5000)).quantize(Decimal("0.01"))
                join_time = timezone.now() - timedelta(days=rng.randint(30, 2200))

                employee = models.Employee.objects.create(
                    name=name,
                    age=age,
                    gender=gender,
                    mobile=mobile,
                    account=account,
                    create_time=join_time,
                    depart=department,
                    is_active=True,
                )
                new_employees.append(employee)

        self.stdout.write(f"新增员工 {len(new_employees)} 人")

        if options["people_only"]:
            self.stdout.write(self.style.SUCCESS("已跳过考勤与薪资生成"))
            self._summary()
            return

        attendance_count = self._create_attendance(new_employees, options["days"], rng)
        salary_count = self._create_salary(new_employees, options["months"], rng)

        self.stdout.write(f"新增考勤 {attendance_count} 条，薪资 {salary_count} 条")
        self._summary()

    # ------------------------------------------------------------------
    # 生成逻辑
    # ------------------------------------------------------------------
    def _make_name(self, rng, gender, used_names) -> str:
        given_pool = GIVEN_FEMALE if gender == 2 else GIVEN_MALE
        for _ in range(200):
            name = rng.choice(SURNAMES) + rng.choice(given_pool)
            if name not in used_names:
                return name
        # 极端情况下（重名太多）加序号保证不重复
        suffix = len(used_names) + 1
        return (rng.choice(SURNAMES) + rng.choice(given_pool))[:14] + str(suffix)

    def _next_mobile(self, existing: set) -> str:
        seq = 1
        while True:
            mobile = f"139{seq:08d}"
            if mobile not in existing:
                return mobile
            seq += 1

    def _create_attendance(self, employees, days: int, rng) -> int:
        if days <= 0:
            return 0
        workdays = self._recent_workdays(days)
        rows = 0
        for employee in employees:
            for workday in workdays:
                roll = rng.random()
                if roll < 0.08:                     # 缺勤：两次都没打卡
                    check_in = None
                    check_out = None
                elif roll < 0.12:                   # 漏打卡（只打一次），按缺勤计
                    check_in = time(rng.randint(8, 9), rng.randint(0, 59))
                    check_out = None
                else:
                    check_in = time(
                        rng.choice([8, 8, 9]),
                        rng.randint(0, 59),
                    )
                    # 9 点整之后上班即迟到
                    if check_in.hour == 9 and check_in.minute == 0:
                        check_in = time(9, rng.randint(1, 40))
                    check_out = time(
                        rng.choice([17, 18, 18, 19]),
                        rng.randint(0, 59),
                    )
                    if check_out.hour == 18 and check_out.minute == 0:
                        check_out = time(18, rng.randint(1, 50))

                models.Attendance.objects.create(
                    employee=employee,
                    date=workday,
                    check_in=check_in,
                    check_out=check_out,
                )
                rows += 1
        return rows

    def _create_salary(self, employees, months: int, rng) -> int:
        if months <= 0:
            return 0
        month_list = self._recent_months(months)
        rows = 0
        for employee in employees:
            low, high = BASE_BY_DEPARTMENT.get(employee.depart.title, DEFAULT_BASE)
            base = Decimal(rng.randrange(low, high + 1, 500))
            for month in month_list:
                bonus = Decimal(rng.randrange(0, 3000, 200))
                deduction = Decimal(rng.choice([0, 0, 0, 100, 200, 300, 500]))
                models.Salary.objects.create(
                    employee=employee,
                    month=month,
                    base_salary=base,
                    bonus=bonus,
                    deduction=deduction,
                    remark=rng.choice(["含季度绩效", "含加班补贴", ""]),
                )
                rows += 1
        return rows

    @staticmethod
    def _recent_workdays(days: int) -> list:
        """从今天往前取 ``days`` 个工作日（跳过周六日），按时间正序返回。"""
        result = []
        cursor = timezone.localdate()
        while len(result) < days:
            if cursor.weekday() < 5:
                result.append(cursor)
            cursor -= timedelta(days=1)
        return list(reversed(result))

    @staticmethod
    def _recent_months(months: int) -> list:
        today = timezone.localdate()
        year, month = today.year, today.month
        result = []
        for _ in range(months):
            result.append(f"{year:04d}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return list(reversed(result))

    def _summary(self):
        self.stdout.write(
            "当前统计：部门 {0} 个 / 员工 {1} 人 / 考勤 {2} 条 / 薪资 {3} 条".format(
                models.Department.objects.count(),
                models.Employee.objects.count(),
                models.Attendance.objects.count(),
                models.Salary.objects.count(),
            )
        )
