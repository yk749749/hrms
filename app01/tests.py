"""单元测试（T12）：覆盖登录、员工 CRUD、考勤状态、薪资计算、权限拦截等关键流程。"""

import json
from datetime import date, time
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from app01 import models
from app01.utils.ai import LLMClient, LLMError, clean_text
from app01.utils.retrieval import extract_keywords


class BaseTestCase(TestCase):
    """公共夹具：部门、员工、三种角色账号。"""

    @classmethod
    def setUpTestData(cls):
        cls.depart = models.Department.objects.create(title="技术部")
        cls.other_depart = models.Department.objects.create(title="市场部")
        cls.employee = models.Employee.objects.create(
            name="张伟",
            age=30,
            gender=1,
            mobile="13800000001",
            account=Decimal("100.00"),
            create_time=timezone.now(),
            depart=cls.depart,
        )

        # 角色与权限
        cls.perm_employee_view = models.Permission.objects.create(
            name="员工-查看", code="employee:view", module="employee"
        )
        cls.perm_employee_add = models.Permission.objects.create(
            name="员工-新增", code="employee:add", module="employee"
        )
        cls.perm_self = models.Permission.objects.create(name="自助-查看", code="self:view", module="self")
        cls.role_manager = models.Role.objects.create(name="部门管理员", code="dept_manager")
        cls.role_manager.permissions.set([cls.perm_employee_view, cls.perm_employee_add])
        cls.role_staff = models.Role.objects.create(name="普通员工", code="staff")
        cls.role_staff.permissions.set([cls.perm_self])

        cls.admin = models.User.objects.create_superuser(
            username="admin", password="admin123456", real_name="管理员"
        )
        cls.manager = models.User.objects.create_user(
            username="manager", password="manager123", department=cls.depart
        )
        cls.manager.roles.set([cls.role_manager])

        cls.staff = models.User.objects.create_user(
            username="staff", password="staff123", employee=cls.employee
        )
        cls.staff.roles.set([cls.role_staff])


class LoginTests(BaseTestCase):
    """T4：登录、验证码、未登录跳转。"""

    def test_login_page_accessible(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "验证码")

    def test_login_requires_correct_captcha(self):
        session = self.client.session
        session["image_code"] = "AB3D"
        session.save()
        response = self.client.post(
            "/login/", {"username": "admin", "password": "admin123456", "code": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "验证码错误")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_success(self):
        session = self.client.session
        session["image_code"] = "AB3D"
        session.save()
        response = self.client.post(
            "/login/", {"username": "admin", "password": "admin123456", "code": "ab3d"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_password_is_hashed(self):
        """数据库中必须是哈希密文，不能是明文。"""
        user = models.User.objects.get(username="admin")
        self.assertNotEqual(user.password, "admin123456")
        self.assertTrue(user.password.startswith("pbkdf2_"))

    def test_protected_page_redirects_to_login(self):
        response = self.client.get("/employee/list/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])


class EmployeeCrudTests(BaseTestCase):
    """T3：员工 CRUD、校验、搜索、筛选。"""

    def setUp(self):
        self.client.force_login(self.admin)

    def test_list_accessible(self):
        response = self.client.get("/employee/list/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "张伟")

    def test_add_valid_employee(self):
        response = self.client.post(
            "/employee/add/",
            {
                "name": "王芳",
                "age": 28,
                "gender": 2,
                "mobile": "13900000002",
                "account": "200.00",
                "create_time": "2026-01-05T09:00",
                "depart": self.depart.id,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(models.Employee.objects.filter(mobile="13900000002").exists())

    def test_add_rejects_invalid_mobile(self):
        response = self.client.post(
            "/employee/add/",
            {
                "name": "李四",
                "age": 30,
                "gender": 1,
                "mobile": "12345",
                "account": "0",
                "create_time": "2026-01-05T09:00",
                "depart": self.depart.id,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "手机号格式不正确")
        self.assertFalse(models.Employee.objects.filter(name="李四").exists())

    def test_add_rejects_duplicate_mobile(self):
        response = self.client.post(
            "/employee/add/",
            {
                "name": "李四",
                "age": 30,
                "gender": 1,
                "mobile": "13800000001",
                "account": "0",
                "create_time": "2026-01-05T09:00",
                "depart": self.depart.id,
                "is_active": "on",
            },
        )
        self.assertContains(response, "该手机号已被使用")

    def test_add_rejects_age_out_of_range(self):
        response = self.client.post(
            "/employee/add/",
            {
                "name": "李四",
                "age": 70,
                "gender": 1,
                "mobile": "13900000003",
                "account": "0",
                "create_time": "2026-01-05T09:00",
                "depart": self.depart.id,
                "is_active": "on",
            },
        )
        self.assertContains(response, "年龄需在 18 - 65 岁之间")

    def test_edit_excludes_self_for_unique_mobile(self):
        """编辑自己时，原手机号不应被判定为重复。"""
        response = self.client.post(
            f"/employee/{self.employee.id}/edit/",
            {
                "name": "张伟",
                "age": 31,
                "gender": 1,
                "mobile": "13800000001",
                "account": "100.00",
                "create_time": "2026-01-05T09:00",
                "depart": self.depart.id,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.age, 31)

    def test_search_and_filter(self):
        response = self.client.get("/employee/list/", {"q": "张"})
        self.assertContains(response, "张伟")
        response = self.client.get("/employee/list/", {"depart": self.other_depart.id})
        self.assertNotContains(response, "张伟")

    def test_delete(self):
        response = self.client.post("/employee/delete/", {"nid": self.employee.id})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(models.Employee.objects.filter(id=self.employee.id).exists())


class AttendanceTests(BaseTestCase):
    """T6：考勤状态自动计算。"""

    def test_status_on_time(self):
        record = models.Attendance(employee=self.employee, date=date(2026, 11, 3),
                                   check_in=time(8, 55), check_out=time(18, 5))
        record.save()
        self.assertEqual(record.status, models.Attendance.STATUS_ON_TIME)

    def test_status_late(self):
        record = models.Attendance(employee=self.employee, date=date(2026, 11, 3),
                                   check_in=time(9, 20), check_out=time(18, 5))
        record.save()
        self.assertEqual(record.status, models.Attendance.STATUS_LATE)

    def test_status_early(self):
        record = models.Attendance(employee=self.employee, date=date(2026, 11, 3),
                                   check_in=time(8, 55), check_out=time(17, 30))
        record.save()
        self.assertEqual(record.status, models.Attendance.STATUS_EARLY)

    def test_status_absent(self):
        record = models.Attendance(employee=self.employee, date=date(2026, 11, 3))
        record.save()
        self.assertEqual(record.status, models.Attendance.STATUS_ABSENT)

    def test_status_late_and_early(self):
        record = models.Attendance(employee=self.employee, date=date(2026, 11, 3),
                                   check_in=time(9, 20), check_out=time(17, 30))
        record.save()
        self.assertEqual(record.status, models.Attendance.STATUS_LATE_EARLY)

    def test_list_page(self):
        self.client.force_login(self.admin)
        models.Attendance.objects.create(employee=self.employee, date=timezone.localdate(),
                                         check_in=time(9, 30), check_out=time(18, 10))
        response = self.client.get("/attendance/list/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "迟到")


class SalaryTests(BaseTestCase):
    """T7：实发工资计算、月度筛选与总额统计。"""

    def setUp(self):
        self.client.force_login(self.admin)

    def test_total_auto_computed_on_create(self):
        self.client.post(
            "/salary/add/",
            {"employee": self.employee.id, "month": "2026-11",
             "base_salary": "8000", "bonus": "1200", "deduction": "300"},
        )
        record = models.Salary.objects.get(employee=self.employee, month="2026-11")
        self.assertEqual(record.total, Decimal("8900.00"))

    def test_month_filter_and_sum(self):
        models.Salary.objects.create(employee=self.employee, month="2026-10",
                                     base_salary=Decimal("8000"), bonus=Decimal("500"), deduction=Decimal("100"))
        models.Salary.objects.create(employee=self.employee, month="2026-11",
                                     base_salary=Decimal("8000"), bonus=Decimal("1000"), deduction=Decimal("0"))
        response = self.client.get("/salary/list/", {"month": "2026-11"})
        self.assertEqual(response.status_code, 200)
        # 11 月总额 9000
        self.assertContains(response, "9,000.00")


class PermissionTests(BaseTestCase):
    """T5：中间件 + 装饰器的接口级权限校验。"""

    def test_staff_cannot_access_employee_module(self):
        self.client.force_login(self.staff)
        response = self.client.get("/employee/list/")
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access_my_profile(self):
        self.client.force_login(self.staff)
        response = self.client.get("/my/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "张伟")

    def test_manager_can_view_employees(self):
        self.client.force_login(self.manager)
        response = self.client.get("/employee/list/")
        self.assertEqual(response.status_code, 200)

    def test_manager_without_delete_permission_denied(self):
        """部门管理员没有“删除”权限时应被装饰器拦截。"""
        self.client.force_login(self.manager)
        response = self.client.post("/employee/delete/", {"nid": self.employee.id})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(models.Employee.objects.filter(id=self.employee.id).exists())

    def test_permission_denied_for_ajax(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            "/task/add/", {"level": 1, "title": "测试", "detail": "测试详情", "leader": self.employee.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(response.content, {"status": False, "error": "您没有访问该模块的权限"})


class TaskAjaxTests(BaseTestCase):
    """T9：AJAX 提交成功返回 JSON，校验失败返回字段错误。"""

    def setUp(self):
        self.client.force_login(self.admin)

    def test_ajax_create_success(self):
        response = self.client.post(
            "/task/add/",
            {"level": 1, "title": "完成薪资核算", "detail": "汇总考勤数据后核算", "leader": self.employee.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["status"])
        self.assertEqual(payload["data"]["title"], "完成薪资核算")

    def test_ajax_validation_error(self):
        response = self.client.post(
            "/task/add/",
            {"level": 1, "title": "x", "detail": "短", "leader": self.employee.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["status"])
        self.assertIn("title", payload["error"])


class DepartmentTests(BaseTestCase):
    """T2：部门 CRUD，以及“有员工时禁止删除”。"""

    def setUp(self):
        self.client.force_login(self.admin)

    def test_add_and_list(self):
        response = self.client.post("/depart/add/", {"title": "财务部", "note": "核算"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(models.Department.objects.filter(title="财务部").exists())

    def test_duplicate_title_rejected(self):
        response = self.client.post("/depart/add/", {"title": "技术部"})
        self.assertContains(response, "该部门已存在")

    def test_delete_protected_when_has_employee(self):
        response = self.client.post("/depart/delete/", {"nid": self.depart.id})
        self.assertContains(response, "该部门下仍有员工")
        self.assertTrue(models.Department.objects.filter(id=self.depart.id).exists())

    def test_delete_empty_department(self):
        empty = models.Department.objects.create(title="行政部")
        response = self.client.post("/depart/delete/", {"nid": empty.id})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(models.Department.objects.filter(id=empty.id).exists())


class AddPeopleCommandTests(BaseTestCase):
    """演示数据补充命令：批量造人，手机号不重复，考勤/薪资随之生成。"""

    def test_add_people_with_records(self):
        from django.core.management import call_command

        before = models.Employee.objects.count()
        call_command("add_people", count=3, days=2, months=2, verbosity=0)
        self.assertEqual(models.Employee.objects.count() - before, 3)

        new_emps = list(models.Employee.objects.order_by("-id")[:3])
        self.assertEqual(len({e.mobile for e in new_emps}), 3)
        for emp in new_emps:
            self.assertEqual(models.Attendance.objects.filter(employee=emp).count(), 2)
            self.assertEqual(models.Salary.objects.filter(employee=emp).count(), 2)
            for record in models.Salary.objects.filter(employee=emp):
                self.assertEqual(record.total, record.base_salary + record.bonus - record.deduction)

    def test_add_people_only(self):
        from django.core.management import call_command

        before = models.Employee.objects.count()
        call_command("add_people", count=2, people_only=True, verbosity=0)
        self.assertEqual(models.Employee.objects.count() - before, 2)
        self.assertEqual(models.Attendance.objects.filter(employee__mobile__startswith="139").count(), 0)


# ---------------------------------------------------------------------------
# AI 智能助手（T1-T7）
# ---------------------------------------------------------------------------
class AIClientUnitTests(SimpleTestCase):
    """不依赖数据库的纯逻辑：输入过滤（T6）与 messages 组装（T5）。"""

    @override_settings(AI_MAX_INPUT=10)
    def test_clean_text_truncates_and_strips(self):
        self.assertEqual(clean_text("  1234567890abc  "), "1234567890")
        self.assertEqual(clean_text(None), "")
        self.assertEqual(clean_text("a\x00b"), "ab")  # 控制字符被剔除

    @override_settings(AI_HISTORY_TURNS=2)
    def test_build_messages_keeps_recent_history(self):
        history = [
            {"role": "user", "content": "第一轮"},
            {"role": "assistant", "content": "答复一"},
            {"role": "user", "content": "第二轮"},
            {"role": "assistant", "content": "答复二"},
            {"role": "user", "content": "第三轮"},
        ]
        messages = LLMClient.build_messages("本轮问题", system="人设", history=history)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1], {"role": "user", "content": "本轮问题"})
        self.assertEqual(len(messages), 1 + 4 + 1)  # 人设 + 最近 2 轮 + 本轮问题
        self.assertNotIn("第一轮", [item["content"] for item in messages])

    @override_settings(AI_API_KEY="")
    def test_chat_without_key_raises_friendly_error(self):
        with self.assertRaises(LLMError) as ctx:
            LLMClient.chat("你好")
        self.assertIn("AI_API_KEY", str(ctx.exception))

    def test_extract_keywords_filters_stopwords(self):
        keywords = extract_keywords("迟到怎么扣钱？")
        self.assertIn("迟到", keywords)
        self.assertNotIn("怎么", keywords)


class AITests(BaseTestCase):
    """四个 AI 接口 + 权限 + 失败兜底：模型调用全部 mock，不联网、不依赖真实 Key。"""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.perm_ai = models.Permission.objects.create(
            name="智能助手-使用", code="ai:view", module="ai"
        )
        cls.role_manager.permissions.add(cls.perm_ai)

        cls.knowledge = models.Knowledge.objects.create(
            title="迟到处理办法",
            category="考勤",
            content="迟到 30 分钟以内当月累计 3 次以上由部门负责人提醒谈话；单次迟到超过 60 分钟按事假半天处理。",
        )
        models.Attendance.objects.create(
            employee=cls.employee,
            date=date(2026, 11, 2),
            check_in=time(9, 20),
            check_out=time(18, 5),
        )
        models.Salary.objects.create(
            employee=cls.employee,
            month="2026-11",
            base_salary=Decimal("8000.00"),
            bonus=Decimal("500.00"),
            deduction=Decimal("100.00"),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    # -- 页面 ----------------------------------------------------------
    @override_settings(AI_API_KEY="")
    def test_page_shows_unconfigured_notice(self):
        response = self.client.get("/ai/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI 智能助手")
        self.assertContains(response, "未配置 API Key")

    def test_staff_without_ai_permission_denied(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/ai/").status_code, 403)

    # -- T2 招聘 JD ----------------------------------------------------
    def test_jd_requires_title(self):
        response = self.client.post("/ai/jd/", {"title": " "})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["status"])

    def test_jd_success(self):
        with mock.patch.object(LLMClient, "chat", return_value="岗位职责：…\n薪资范围：15-25K") as mocked:
            response = self.client.post("/ai/jd/", {"title": "Java 后端工程师", "department": "技术部"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["status"])
        self.assertIn("薪资范围", payload["data"])
        prompt_text = mocked.call_args.args[0]
        self.assertIn("Java 后端工程师", prompt_text)
        self.assertIn("技术部", prompt_text)

    def test_llm_failure_returns_friendly_error(self):
        with mock.patch.object(LLMClient, "chat", side_effect=LLMError("AI 服务响应超时，请检查网络后重试。")):
            response = self.client.post("/ai/jd/", {"title": "产品经理"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["status"])
        self.assertIn("超时", payload["error"])

    # -- T3 制度问答 ---------------------------------------------------
    def test_qa_without_knowledge_returns_unknown(self):
        response = self.client.post("/ai/qa/", {"question": "年会抽奖怎么报名？"})
        payload = response.json()
        self.assertTrue(payload["status"])
        self.assertEqual(payload["data"], "不知道")
        self.assertEqual(payload["sources"], [])

    def test_qa_with_knowledge_injects_context(self):
        with mock.patch.object(LLMClient, "chat", return_value="迟到 30 分钟内提醒谈话。") as mocked:
            response = self.client.post("/ai/qa/", {"question": "迟到怎么处理？"})
        payload = response.json()
        self.assertTrue(payload["status"])
        self.assertEqual(len(payload["sources"]), 1)
        self.assertEqual(payload["sources"][0]["title"], "迟到处理办法")
        prompt_text = mocked.call_args.args[0]
        self.assertIn("《迟到处理办法》", prompt_text)
        self.assertIn("部门负责人", prompt_text)

    # -- T4 数据点评 ---------------------------------------------------
    def test_comment_injects_attendance_and_salary(self):
        with mock.patch.object(LLMClient, "chat", return_value="点评：出勤基本正常。\n建议：注意打卡时间。") as mocked:
            response = self.client.post(
                "/ai/comment/", {"employee": self.employee.id, "month": "2026-11"}
            )
        payload = response.json()
        self.assertTrue(payload["status"])
        self.assertIn("迟到 1 次", payload["data_text"])
        self.assertIn("实发 8400.00 元", payload["data_text"])
        self.assertIn("迟到 1 次", mocked.call_args.args[0])

    def test_comment_without_records(self):
        response = self.client.post("/ai/comment/", {"employee": self.employee.id, "month": "2025-01"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["status"])

    # -- T5 多轮对话 ---------------------------------------------------
    def test_chat_passes_history_and_drops_duplicate(self):
        history = [
            {"role": "user", "content": "迟到怎么算？"},
            {"role": "assistant", "content": "晚于 09:00 记迟到。"},
            {"role": "user", "content": "那如果缺勤呢？"},
        ]
        with mock.patch.object(LLMClient, "chat", return_value="缺勤按日扣基本工资。") as mocked:
            response = self.client.post(
                "/ai/chat/",
                {"question": "那如果缺勤呢？", "history": json.dumps(history)},
            )
        payload = response.json()
        self.assertTrue(payload["status"])
        passed_history = mocked.call_args.kwargs["history"]
        self.assertEqual(len(passed_history), 2)  # 末尾重复的本轮问题被去掉
        self.assertEqual(passed_history[-1]["content"], "晚于 09:00 记迟到。")

    # -- T6 输入过滤 ---------------------------------------------------
    @override_settings(AI_MAX_INPUT=10)
    def test_chat_input_is_truncated(self):
        with mock.patch.object(LLMClient, "chat", return_value="收到") as mocked:
            response = self.client.post("/ai/chat/", {"question": "一" * 30})
        payload = response.json()
        self.assertTrue(payload["status"])
        self.assertEqual(len(mocked.call_args.args[0]), 10)

    # -- T7 SSE 流式 ---------------------------------------------------
    def test_stream_returns_sse_events(self):
        # 注意：StreamingHttpResponse 的生成器是“惰性”的，必须在 patch 仍生效时消费完，
        # 否则退出 with 后 mock 已还原，会真的去调用模型。
        with mock.patch.object(LLMClient, "chat_stream", return_value=iter(["你", "好"])):
            response = self.client.post("/ai/chat/stream/", {"question": "你好"})
            body = b"".join(response.streaming_content).decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertIn('"delta": "你"', body)
        self.assertIn('"done": true', body)
