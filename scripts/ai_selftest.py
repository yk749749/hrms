"""T1 验收脚本：验证环境变量与 LLMClient 封装是否打通。

用法（建议与 runserver 在同一个 PowerShell 窗口，或先执行 ``. .\\scripts\\ai_env.ps1``）::

    E:\\work_down\\python\\python.exe scripts\\ai_selftest.py
    E:\\work_down\\python\\python.exe scripts\\ai_selftest.py "用一句话介绍你自己"
    E:\\work_down\\python\\python.exe scripts\\ai_selftest.py --stream "写一句上班提醒"

脚本只做两件事：打印当前配置（不打印 Key 本身），然后调用一次模型并输出回答；
失败时把友好提示打出来并以退出码 1 结束，方便在验收表里记录。
"""

import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hrms.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from app01.utils.ai import LLMClient, LLMError  # noqa: E402


def main() -> int:
    args = [item for item in sys.argv[1:] if item != "--stream"]
    use_stream = "--stream" in sys.argv[1:]
    prompt = args[0] if args else "用一句话介绍你自己"

    print(f"模型    : {settings.AI_MODEL}")
    print(f"接口    : {settings.AI_BASE_URL}")
    if LLMClient.is_configured():
        print(f"API Key : 已配置（长度 {len(settings.AI_API_KEY)}）")
    else:
        print("API Key : 未配置 —— 请先在本窗口执行  . .\\scripts\\ai_env.ps1")
    print(f"输入    : {prompt}\n")

    started = time.time()
    try:
        if use_stream:
            print("回答（流式）: ", end="", flush=True)
            for chunk in LLMClient.chat_stream(prompt):
                print(chunk, end="", flush=True)
            print()
        else:
            print("回答: " + LLMClient.chat(prompt))
    except LLMError as exc:
        print(f"\n[失败] {exc}")
        print("提示：这是友好兜底文本，页面上也会这样提示，不会报错崩溃。")
        return 1

    print(f"\n[耗时] {time.time() - started:.2f} 秒")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
