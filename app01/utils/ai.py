# app01/utils/ai.py
"""大模型统一封装（T1）：把大模型当成“一个会写字的接口”——``chat(提示词) -> 文本``。

设计要点（答辩时可讲的三点）：

1. **配置全部走环境变量**：``AI_API_KEY`` / ``AI_BASE_URL`` / ``AI_MODEL`` 在
   ``hrms/settings.py`` 里从 ``os.environ`` 读取，代码里不出现任何 Key，
   因此可以放心提交 Git；
2. **懒加载单例客户端**：同一进程只建一个 ``OpenAI`` 客户端，换服务商只要改
   ``AI_BASE_URL``（都兼容 OpenAI 接口协议）；
3. **异常统一收口**：所有网络 / 鉴权 / 限流 / 超时错误都包装成 :class:`LLMError`，
   异常文本就是能直接展示的中文提示，视图层不必再判断异常类型，页面不会崩。
"""

from __future__ import annotations

import logging
import re
from typing import Iterator

from django.conf import settings

logger = logging.getLogger("hrms.ai")

# 除常见空白外的控制字符统一剔除（防止不可见字符把提示词“污染”）
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class LLMError(Exception):
    """大模型调用失败。异常文本本身就是可直接展示给用户的中文提示。"""


def clean_text(value, limit=None) -> str:
    """规整用户输入（T6）：剔除控制字符、去掉首尾空白、按上限截断。

    :param value: 原始输入（可能是 None / 数字 / 任意对象）
    :param limit: 字符上限，默认取 ``settings.AI_MAX_INPUT``（400）
    """
    if value is None:
        return ""
    text = _CONTROL_CHARS.sub("", str(value)).strip()
    limit = settings.AI_MAX_INPUT if limit is None else limit
    if limit and len(text) > limit:
        text = text[:limit]
    return text


class LLMClient:
    """统一的大模型调用入口，全站只通过它访问模型。"""

    _client = None

    # -- 基础能力 --------------------------------------------------------
    @classmethod
    def is_configured(cls) -> bool:
        """是否已配置 API Key（页面用它决定显示“已连接 / 未配置”）。"""
        return bool((getattr(settings, "AI_API_KEY", "") or "").strip())

    @classmethod
    def _get_client(cls):
        """懒加载客户端：第一次调用时才创建，之后复用同一实例。"""
        if not cls.is_configured():
            raise LLMError(
                "尚未配置 AI_API_KEY：请先在 PowerShell 里执行 . .\\scripts\\ai_env.ps1 "
                "（或写入系统环境变量），再重启服务。"
            )
        if cls._client is None:
            try:
                from openai import OpenAI  # 延迟导入：未装依赖也不影响项目其他模块启动
            except ImportError as exc:  # pragma: no cover - 依赖缺失时才会走到
                raise LLMError("缺少 openai 依赖，请先执行：pip install openai") from exc

            cls._client = OpenAI(
                api_key=settings.AI_API_KEY,
                base_url=getattr(settings, "AI_BASE_URL", "") or None,
                timeout=getattr(settings, "AI_TIMEOUT", 30),
                max_retries=1,  # 失败只重试一次，避免页面长时间转圈
            )
        return cls._client

    # -- 消息组装 --------------------------------------------------------
    @classmethod
    def build_messages(cls, prompt, system=None, history=None) -> list[dict]:
        """把「人设 + 历史 + 本轮问题」组装成 messages 列表。

        ``history`` 只接受 ``{"role": "user"/"assistant", "content": str}`` 形状，
        角色非 assistant 的一律按 user 处理，内容为空的消息直接丢弃——既不信任前端，
        也顺手完成“只保留最近 N 轮”的裁剪。
        """
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": str(system)})

        keep = max(getattr(settings, "AI_HISTORY_TURNS", 4), 0) * 2
        cleaned = []
        for item in history or []:
            if not isinstance(item, dict):
                continue
            content = clean_text(item.get("content", ""), limit=600)
            if not content:
                continue
            role = "assistant" if item.get("role") == "assistant" else "user"
            cleaned.append({"role": role, "content": content})
        if keep:
            cleaned = cleaned[-keep:]

        messages.extend(cleaned)
        messages.append({"role": "user", "content": str(prompt)})
        return messages

    # -- 一次性调用 ------------------------------------------------------
    @classmethod
    def chat(cls, prompt, system=None, history=None, temperature=None, max_tokens=None) -> str:
        """发送提示词，返回模型生成的文字（失败抛 :class:`LLMError`）。"""
        text = clean_text(prompt)
        if not text:
            raise LLMError("提示词不能为空")

        messages = cls.build_messages(text, system=system, history=history)
        payload = {
            "model": settings.AI_MODEL,
            "messages": messages,
            "temperature": getattr(settings, "AI_TEMPERATURE", 0.7)
            if temperature is None
            else temperature,
            "max_tokens": getattr(settings, "AI_MAX_TOKENS", 800)
            if max_tokens is None
            else max_tokens,
        }

        try:
            resp = cls._get_client().chat.completions.create(**payload)
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 - 统一转成友好提示，绝不把栈抛给页面
            logger.warning("LLM 调用失败 model=%s err=%s", settings.AI_MODEL, exc)
            raise cls._friendly_error(exc) from exc

        try:
            answer = (resp.choices[0].message.content or "").strip()
        except (AttributeError, IndexError) as exc:  # 模型返回结构异常也要给出明确提示
            logger.warning("LLM 返回结构异常 model=%s", settings.AI_MODEL)
            raise LLMError("模型返回内容格式异常，请稍后再试。") from exc
        if not answer:
            raise LLMError("模型没有返回内容，请换个说法再试。")
        logger.info("LLM 调用成功 model=%s prompt_len=%s answer_len=%s",
                    settings.AI_MODEL, len(text), len(answer))
        return answer

    # -- 流式调用（T7） --------------------------------------------------
    @classmethod
    def chat_stream(cls, prompt, system=None, history=None, temperature=None) -> Iterator[str]:
        """流式调用：返回“逐段产出文字”的迭代器，供 SSE 逐字输出使用。"""
        text = clean_text(prompt)
        if not text:
            raise LLMError("提示词不能为空")

        payload = {
            "model": settings.AI_MODEL,
            "messages": cls.build_messages(text, system=system, history=history),
            "temperature": getattr(settings, "AI_TEMPERATURE", 0.7)
            if temperature is None
            else temperature,
            "stream": True,
        }
        try:
            stream = cls._get_client().chat.completions.create(**payload)
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 流式调用建立失败 model=%s err=%s", settings.AI_MODEL, exc)
            raise cls._friendly_error(exc) from exc
        return cls._iter_chunks(stream)

    @staticmethod
    def _iter_chunks(stream) -> Iterator[str]:
        """把 SDK 返回的 chunk 流拆成纯文本片段；中途出错同样转成友好提示。"""
        try:
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None) if delta else None
                if content:
                    yield content
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 流式读取中断 err=%s", exc)
            raise LLMClient._friendly_error(exc) from exc

    # -- 异常翻译 --------------------------------------------------------
    @staticmethod
    def _friendly_error(exc: Exception) -> LLMError:
        """把 SDK 异常翻译成一句用户看得懂的话（按类名 + 文本双重判断，不依赖具体版本）。"""
        name = type(exc).__name__
        message = str(exc)
        lower = message.lower()

        if "Authentication" in name or "invalid_api_key" in lower or "401" in message:
            return LLMError("AI 服务鉴权失败：请检查 AI_API_KEY 是否正确、是否已过期。")
        if "RateLimit" in name or "429" in message or "rate limit" in lower:
            return LLMError("AI 服务调用过于频繁（限流），请稍等几秒再试。")
        if "Timeout" in name or "timed out" in lower:
            return LLMError("AI 服务响应超时，请检查网络后重试。")
        if "NotFound" in name or "404" in message:
            return LLMError("AI 接口地址或模型名有误，请检查 AI_BASE_URL / AI_MODEL。")
        if "Connection" in name or "connect" in lower or "getaddrinfo" in lower:
            return LLMError("无法连接 AI 服务，请检查网络与 AI_BASE_URL。")
        if "BadRequest" in name or "400" in message:
            return LLMError("AI 服务拒绝了本次请求（参数或内容不合规），请调整后重试。")
        return LLMError(f"AI 服务调用失败（{name}），请稍后再试。")
