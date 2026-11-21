# app01/management/commands/demo_data.py
"""一键写入演示数据，便于各阶段自测与界面展示。

用法::

    python manage.py demo_data            # 数据库为空时写入
    python manage.py demo_data --force    # 先清空业务数据再写入
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from app01 import models

User = get_user_model()

DEPARTMENTS = [
    ("技术部", "后端、前端与运维"),
    ("市场部", "市场推广与客户拓展"),
    ("人事部", "招聘、培训与员工关系"),
    ("财务部", "核算、报销与预算"),
]

EMPLOYEES = [
    ("张伟", 1, 32, "13800000001", "技术部", Decimal("1200.00")),
    ("王芳", 2, 28, "13800000002", "技术部", Decimal("980.50")),
    ("李强", 1, 35, "13800000003", "技术部", Decimal("2300.00")),
    ("赵敏", 2, 26, "13800000004", "市场部", Decimal("560.00")),
    ("刘洋", 1, 40, "13800000005", "市场部", Decimal("1500.00")),
    ("陈静", 2, 31, "13800000006", "市场部", Decimal("760.00")),
    ("杨帆", 1, 24, "13800000007", "人事部", Decimal("320.00")),
    ("周宁", 2, 29, "13800000008", "人事部", Decimal("880.00")),
    ("吴磊", 1, 38, "13800000009", "财务部", Decimal("1980.00")),
    ("徐丽", 2, 33, "13800000010", "财务部", Decimal("1120.00")),
    ("孙浩", 1, 27, "13800000011", "技术部", Decimal("640.00")),
    ("马欣", 2, 22, "13800000012", "财务部", Decimal("180.00")),
]

ANNOUNCEMENTS = [
    ("关于 11 月薪酬发放时间的通知", "本月薪资将于 11 月 10 日统一发放，请大家及时核对个人薪资明细，如有疑问请联系财务部。", True),
    ("年度体检安排", "公司年度体检定于 11 月 20 日进行，请各部门于本周五前完成报名统计，体检当天请携带身份证。", True),
    ("考勤打卡规范提醒", "请各位同事严格按照 09:00 - 18:00 的工作时间打卡，漏打卡需当天提交补卡说明，否则按缺勤处理。", False),
    ("新员工入职培训通知", "本月新入职员工培训将于下周三下午 14:00 在三楼会议室举行，请相关部门负责人准时参加。", False),
    ("办公区网络升级", "技术部将于本周六对办公区网络进行升级，期间可能短暂断网，请提前保存工作内容。", False),
]

TASKS = [
    ("完成 11 月薪资核算", "汇总各部门考勤数据，完成本月薪资核算并提交财务复核。", 1),
    ("整理年度招聘计划", "输出明年各部门岗位需求与预算，形成招聘计划表。", 2),
    ("优化考勤统计报表", "考勤列表增加按状态筛选与月度汇总，提升统计效率。", 2),
    ("更新员工手册", "结合最新考勤与请假制度，更新员工手册相关章节。", 3),
    ("组织季度团建", "确定团建时间、地点与预算，收集各部门报名意向。", 3),
]


class Command(BaseCommand):
    help = "写入演示数据（部门、员工、考勤、薪资、公告、任务、演示账号）"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="先清空业务数据再写入")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["force"]:
            models.Task.objects.all().delete()
            models.Announcement.objects.all().delete()
            models.Salary.objects.all().delete()
            models.Attendance.objects.all().delete()
            models.Employee.objects.all().delete()
            models.Department.objects.all().delete()
            self.stdout.write("已清空原有业务数据")

        if models.Employee.objects.exists() and not options["force"]:
            self.stdout.write(self.style.WARNING("已存在员工数据，跳过写入（需要重置请加 --force）"))
            return

        # 1. 部门
        dept_map = {}
        for title, note in DEPARTMENTS:
            dept_map[title], _ = models.Department.objects.get_or_create(title=title, defaults={"note": note})
        self.stdout.write(f"部门：{len(dept_map)} 个")

        # 2. 员工
        today = timezone.localdate()
        employee_map = {}
        for name, gender, age, mobile, dept_title, account in EMPLOYEES:
            employee_map[name], _ = models.Employee.objects.get_or_create(
                mobile=mobile,
                defaults={
                    "name": name,
                    "gender": gender,
                    "age": age,
                    "depart": dept_map[dept_title],
                    "account": account,
                    "create_time": timezone.make_aware(
                        datetime.combine(today - timedelta(days=random.randint(120, 900)), time(9, 0))
                    ),
                },
            )
        self.stdout.write(f"员工：{len(employee_map)} 人")

        # 3. 考勤（最近 30 天的工作日）
        created_att = 0
        for employee in employee_map.values():
            for offset in range(30):
                day = today - timedelta(days=offset)
                if day.weekday() >= 5:  # 周末不打卡
                    continue
                if models.Attendance.objects.filter(employee=employee, date=day).exists():
                    continue
                # 80% 正常，其余制造迟到 / 早退 / 缺勤
                roll = random.random()
                if roll < 0.08:
                    check_in, check_out = None, None
                elif roll < 0.16:
                    check_in, check_out = time(9, random.randint(5, 40)), time(18, 10)
                elif roll < 0.22:
                    check_in, check_out = time(8, 50), time(17, random.randint(0, 40))
                else:
                    check_in = time(8, random.randint(30, 59))
                    check_out = time(18, random.randint(0, 50))
                models.Attendance.objects.create(
                    employee=employee, date=day, check_in=check_in, check_out=check_out
                )
                created_att += 1
        self.stdout.write(f"考勤：{created_att} 条")

        # 4. 薪资（最近 6 个月）
        created_salary = 0
        base_map = {
            "张伟": 12000, "王芳": 9500, "李强": 15000, "赵敏": 8000, "刘洋": 13000,
            "陈静": 8500, "杨帆": 7000, "周宁": 8800, "吴磊": 14000, "徐丽": 10000,
            "孙浩": 7600, "马欣": 6800,
        }
        year, month = today.year, today.month
        months = []
        for _ in range(6):
            months.append(f"{year}-{month:02d}")
            month -= 1
            if month == 0:
                year, month = year - 1, 12

        for name, employee in employee_map.items():
            for m in months:
                if models.Salary.objects.filter(employee=employee, month=m).exists():
                    continue
                base = Decimal(base_map.get(name, 8000))
                bonus = Decimal(random.choice([0, 500, 800, 1200, 2000]))
                deduction = Decimal(random.choice([0, 0, 100, 300, 500]))
                models.Salary.objects.create(
                    employee=employee, month=m, base_salary=base, bonus=bonus, deduction=deduction,
                    remark="演示数据",
                )
                created_salary += 1
        self.stdout.write(f"薪资：{created_salary} 条")

        # 5. 公告
        admin_user = User.objects.filter(is_superuser=True).first()
        for title, content, is_top in ANNOUNCEMENTS:
            models.Announcement.objects.get_or_create(
                title=title, defaults={"content": content, "is_top": is_top, "publisher": admin_user}
            )
        self.stdout.write(f"公告：{models.Announcement.objects.count()} 条")

        # 6. 任务
        leaders = list(employee_map.values())
        for title, detail, level in TASKS:
            models.Task.objects.get_or_create(
                title=title,
                defaults={
                    "detail": detail,
                    "level": level,
                    "leader": random.choice(leaders),
                    "create_by": admin_user,
                },
            )
        self.stdout.write(f"任务：{models.Task.objects.count()} 条")

        # 7. 演示账号：部门管理员 + 普通员工
        dept_mgr, _ = User.objects.get_or_create(
            username="deptmgr",
            defaults={"real_name": "技术部主管", "department": dept_map["技术部"]},
        )
        dept_mgr.set_password("deptmgr123")
        dept_mgr.department = dept_map["技术部"]
        dept_mgr.save()
        role = models.Role.objects.filter(code="dept_manager").first()
        if role:
            dept_mgr.roles.set([role])

        staff, _ = User.objects.get_or_create(
            username="staff",
            defaults={"real_name": "张伟", "employee": employee_map["张伟"]},
        )
        staff.set_password("staff123")
        staff.employee = employee_map["张伟"]
        staff.save()
        role = models.Role.objects.filter(code="staff").first()
        if role:
            staff.roles.set([role])

        self.stdout.write(
            self.style.SUCCESS(
                "演示账号：deptmgr / deptmgr123（部门管理员）、staff / staff123（普通员工）"
            )
        )
        self.stdout.write(self.style.SUCCESS("demo_data 执行完成"))
