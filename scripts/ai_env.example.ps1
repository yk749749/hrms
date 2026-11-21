# scripts/ai_env.example.ps1
# 方式 A 模板：复制成 ai_env.ps1 后填入自己的 Key（ai_env.ps1 已加入 .gitignore，不会入库）。
#
# 用法（注意开头有一个点 "."，表示在当前窗口执行；不加点变量会随子进程退出而丢失）：
#     cd E:\hrms
#     Copy-Item .\scripts\ai_env.example.ps1 .\scripts\ai_env.ps1
#     notepad .\scripts\ai_env.ps1          # 填好 Key 后保存
#     . .\scripts\ai_env.ps1
#
# 重要：本文件必须保存为“UTF-8 带 BOM”。Windows PowerShell 5.1 读取无 BOM 的 UTF-8 会按 GBK 解码，
# 中文全部乱码并报语法错误（如“数组索引表达式丢失或无效”）。

$env:AI_API_KEY  = "sk-在这里填入你的_API_Key"
$env:AI_BASE_URL = "https://api.siliconflow.cn/v1"
# 演示建议用 Qwen2.5-7B-Instruct（1-3 秒）；想要更强推理可换 deepseek-ai/DeepSeek-R1-0528-Qwen3-8B（单次约 17 秒）
$env:AI_MODEL    = "Qwen/Qwen2.5-7B-Instruct"

# 可选参数（一般不用改，需要时取消注释）
# $env:AI_TIMEOUT       = "30"    # 单次调用超时（秒）
# $env:AI_TEMPERATURE   = "0.7"   # 随机度：越低越稳定
# $env:AI_MAX_TOKENS    = "800"   # 单次最多生成多少 token
# $env:AI_MAX_INPUT     = "400"   # 单条用户输入最多多少字符（T6 输入过滤）
# $env:AI_HISTORY_TURNS = "4"     # 多轮对话保留最近几轮（T5）

if ($env:AI_API_KEY -like "*填入*" -or [string]::IsNullOrWhiteSpace($env:AI_API_KEY)) {
    Write-Host "[提示] AI_API_KEY 仍是占位符，请先编辑 scripts\ai_env.ps1 填入真实 Key。" -ForegroundColor Yellow
} else {
    $keyLen = $env:AI_API_KEY.Length
    Write-Host "[OK] 已设置 AI_API_KEY (长度 $keyLen)" -ForegroundColor Green
    Write-Host "[OK] AI_BASE_URL = $env:AI_BASE_URL"
    Write-Host "[OK] AI_MODEL    = $env:AI_MODEL"
    Write-Host "下一步： E:\work_down\python\python.exe manage.py runserver 127.0.0.1:8000"
}

# 若希望“永久生效”（方式 B），可在 PowerShell 里执行下面两行后重开终端：
#   [Environment]::SetEnvironmentVariable("AI_API_KEY", "你的_Key", "User")
#   [Environment]::SetEnvironmentVariable("AI_MODEL", "Qwen/Qwen2.5-7B-Instruct", "User")
