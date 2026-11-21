# app01/views/ai.py
"""AI 智能助手（T1-T7）：招聘 JD / 制度问答 / 数据点评 / 多轮对话（含 SSE 流式）。

四个页面模块共用同一个 :class:`~app01.utils.ai.LLMClient`，区别只有“提示词怎么写、
要不要先查库”。所有接口统一返回 JSON：

- 成功：``{"status": true, "data": "...", ...}``
- 参数错误：HTTP 400 + ``{"status": false, "error": "..."}``
- 模型调用失败：HTTP 200 + ``{"status": false, "error": "..."}``（前端直接回显，不弹栈）
"""

import json
import logging
import re

from django.conf import settings
from django.db.models import Count, Q
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils import timezone

from app01 import models
from app01.utils.ai import LLMClient, LLMError, clean_text
from app01.utils.decorators import require_perm
from app01.utils.prompts import (
    CHAT_SYSTEM,
    COMMENT_SYSTEM,
    JD_SYSTEM,
    QA_SYSTEM,
    build_data_comment_prompt,
    build_jd_prompt,
    build_qa_prompt,
)
from app01.utils.retrieval import build_context, search_knowledge
from app01.utils.scope import (
    attendance_queryset_for,
    employee_queryset_for,
    salary_queryset_for,
)

logger = logging.getLogger("hrms.ai")

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------
def _ok(data, **extra):
    """业务成功：数据放在 data 里，附加字段（如检索来源）平铺在顶层。"""
    payload = {"status": True, "data": data}
    payload.update(extra)
    return JsonResponse(payload)


def _err(message, status=200):
    """业务失败：默认 HTTP 200（前端按 status 判断），参数错误用 400 区分。"""
    return JsonResponse({"status": False, "error": message}, status=status)


def _load_history(raw, question=""):
    """把前端回传的 history 解析、清洗成安全的对话列表（T5/T6）。

    前端每次只传“本轮之前”的历史；如果它多传了本轮问题，这里再做一次去重，
    避免同一句话在提示词里出现两遍。
    """
    try:
        items = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(items, list):
        return []

    keep = max(getattr(settings, "AI_HISTORY_TURNS", 4), 0) * 2
    cleaned = []
    for item in items[-keep:]:
        if not isinstance(item, dict):
            continue
        role = "assistant" if item.get("role") == "assistant" else "user"
        content = clean_text(item.get("content", ""), limit=600)
        if content:
            cleaned.append({"role": role, "content": content})

    if cleaned and cleaned[-1]["role"] == "user" and cleaned[-1]["content"] == question:
        cleaned.pop()
    return cleaned


def _recent_months():
    """数据点评下拉框用的月份列表（最近 12 个月 + 库中已有月份，倒序）。"""
    months = set(models.Salary.objects.values_list("month", flat=True).distinct())
    today = timezone.localdate()
    year, month = today.year, today.month
    for _ in range(12):
        months.add(f"{year}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return sorted(months, reverse=True)


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------
@require_perm("ai:view")
def ai_page(request):
    """AI 智能助手主页：四个标签页共用一页，便于答辩演示。"""
    context = {
        "configured": LLMClient.is_configured(),
        "model_name": settings.AI_MODEL,
        "base_url": settings.AI_BASE_URL,
        "max_input": settings.AI_MAX_INPUT,
        "history_turns": settings.AI_HISTORY_TURNS,
        "employees": employee_queryset_for(request.user)
        .filter(is_active=True)
        .order_by("name"),
        "months": _recent_months(),
        "default_month": timezone.localdate().strftime("%Y-%m"),
        "knowledges": models.Knowledge.objects.all(),
        "knowledge_count": models.Knowledge.objects.count(),
    }
    return render(request, "ai/index.html", context)


# ---------------------------------------------------------------------------
# 模块 A：智能生成招聘 JD（T2）
# ---------------------------------------------------------------------------
@require_perm("ai:view")
def generate_jd(request):
    """输入岗位名称，返回结构化招聘 JD（AI 只负责写，不落库）。"""
    if request.method != "POST":
        return _err("请使用 POST 提交", status=405)

    title = clean_text(request.POST.get("title", ""), limit=40)
    department = clean_text(request.POST.get("department", ""), limit=32)
    if not title:
        return _err("岗位名称不能为空", status=400)
    if len(title) < 2:
        return _err("岗位名称至少 2 个字", status=400)

    try:
        text = LLMClient.chat(
            build_jd_prompt(title, department),
            system=JD_SYSTEM,
            temperature=0.6,
        )
    except LLMError as exc:
        return _err(str(exc))
    return _ok(text, title=title)


# ---------------------------------------------------------------------------
# 模块 B：制度知识库问答（T3）
# ---------------------------------------------------------------------------
@require_perm("ai:view")
def knowledge_qa(request):
    """提问 -> 关键词检索知识库 -> 资料拼进提示词 -> 模型只依据资料回答。"""
    if request.method != "POST":
        return _err("请使用 POST 提交", status=405)

    question = clean_text(request.POST.get("question", ""))
    if not question:
        return _err("问题不能为空", status=400)

    hits = search_knowledge(question, limit=3)
    sources = [
        {"id": item.id, "title": item.title, "category": item.category}
        for item in hits
    ]

    # 没检索到资料：直接兜底“不知道”，既不浪费一次调用，也避免模型自由发挥
    if not hits:
        return _ok(
            "不知道",
            sources=[],
            hint="知识库中没有检索到相关制度，建议联系人事部门确认，或补充该制度条目。",
        )

    try:
        text = LLMClient.chat(
            build_qa_prompt(question, build_context(hits)),
            system=QA_SYSTEM,
            temperature=0.2,  # 问答场景要稳定，随机度调低
        )
    except LLMError as exc:
        return _err(str(exc))
    return _ok(text, sources=sources)


# ---------------------------------------------------------------------------
# 模块 C：数据智能点评（T4）
# ---------------------------------------------------------------------------
@require_perm("ai:view")
def data_comment(request):
    """读取某员工某月的考勤 + 薪资数据，转成文本注入提示词，生成点评。"""
    if request.method != "POST":
        return _err("请使用 POST 提交", status=405)

    employee_id = clean_text(request.POST.get("employee", ""), limit=20)
    month = clean_text(request.POST.get("month", ""), limit=7) or timezone.localdate().strftime("%Y-%m")

    if not employee_id.isdigit():
        return _err("请选择要点评的员工", status=400)
    if not _MONTH_RE.match(month):
        return _err("月份格式应为 YYYY-MM（例如 2026-11）", status=400)

    # 数据范围：沿用项目既有的 scope 规则（超管全量 / 部门管理员本部门 / 员工本人）
    employee = employee_queryset_for(request.user).filter(pk=int(employee_id)).first()
    if not employee:
        return _err("未找到该员工，或当前账号没有查看该员工数据的权限", status=400)

    year, month_no = int(month[:4]), int(month[5:7])
    attendance_stats = attendance_queryset_for(request.user).filter(
        employee=employee, date__year=year, date__month=month_no
    ).aggregate(
        total=Count("id"),
        on_time=Count("id", filter=Q(status=models.Attendance.STATUS_ON_TIME)),
        late=Count("id", filter=Q(status=models.Attendance.STATUS_LATE)),
        early=Count("id", filter=Q(status=models.Attendance.STATUS_EARLY)),
        absent=Count("id", filter=Q(status=models.Attendance.STATUS_ABSENT)),
        late_early=Count("id", filter=Q(status=models.Attendance.STATUS_LATE_EARLY)),
    )
    salary = salary_queryset_for(request.user).filter(employee=employee, month=month).first()

    if not attendance_stats["total"] and salary is None:
        return _err("该员工本月既没有考勤记录，也没有薪资记录，暂时无法点评", status=400)

    # 结构化数据 -> 可读文本（这一步就是“上下文注入”）
    lines = [f"员工：{employee.name}（{employee.depart.title}），统计月份：{month}。"]
    if attendance_stats["total"]:
        lines.append(
            "考勤：共 {total} 条记录 —— 按时 {on_time} 次、迟到 {late} 次、早退 {early} 次、"
            "缺勤 {absent} 次、迟到并早退 {late_early} 次。".format(**attendance_stats)
        )
    else:
        lines.append("考勤：本月没有考勤记录。")
    if salary:
        lines.append(
            f"薪资：基本工资 {salary.base_salary} 元、奖金 {salary.bonus} 元、"
            f"扣款 {salary.deduction} 元、实发 {salary.total} 元。"
        )
    else:
        lines.append("薪资：本月尚未录入薪资记录。")
    data_text = "\n".join(lines)

    try:
        text = LLMClient.chat(
            build_data_comment_prompt(data_text),
            system=COMMENT_SYSTEM,
            temperature=0.4,
            max_tokens=300,
        )
    except LLMError as exc:
        return _err(str(exc))
    return _ok(text, data_text=data_text, employee=employee.name, month=month)


# ---------------------------------------------------------------------------
# 模块 D：多轮对话助手（T5）
# ---------------------------------------------------------------------------
@require_perm("ai:view")
def chat(request):
    """带历史的多轮对话：history 由前端回传（服务端仍会裁剪与清洗）。"""
    if request.method != "POST":
        return _err("请使用 POST 提交", status=405)

    question = clean_text(request.POST.get("question", ""))
    if not question:
        return _err("问题不能为空", status=400)

    history = _load_history(request.POST.get("history"), question)
    try:
        text = LLMClient.chat(question, system=CHAT_SYSTEM, history=history, temperature=0.6)
    except LLMError as exc:
        return _err(str(exc))
    return _ok(text, history_used=len(history))


# ---------------------------------------------------------------------------
# 模块 E：流式输出（T7 SSE）
# ---------------------------------------------------------------------------
def _sse(payload):
    """把一个字典编码成一条 SSE 事件（data 必须是单行 JSON）。"""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


@require_perm("ai:view")
def chat_stream(request):
    """流式对话：逐词推送，前端用 fetch + ReadableStream 边收边渲染。"""
    if request.method != "POST":
        return _err("请使用 POST 提交", status=405)

    question = clean_text(request.POST.get("question", ""))
    if not question:
        return _err("问题不能为空", status=400)

    history = _load_history(request.POST.get("history"), question)

    def event_stream():
        # 先发一个 start，前端可据此把气泡切到“输入中”状态
        yield _sse({"event": "start"})
        try:
            for token in LLMClient.chat_stream(question, system=CHAT_SYSTEM, history=history):
                yield _sse({"delta": token})
        except LLMError as exc:
            yield _sse({"error": str(exc)})
        except Exception:  # noqa: BLE001 - 流中途异常也要给前端一个明确信号
            logger.exception("SSE 流式输出异常")
            yield _sse({"error": "AI 服务暂时不可用，请稍后再试。"})
        yield _sse({"done": True})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # 关掉反向代理缓冲，保证逐字效果
    return response
