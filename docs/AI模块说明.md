# AI 智能助手模块说明（任务书 T1–T7）

> 对应《基于大模型的智能员工助手课程设计任务书》。本模块在既有 HRMS 项目上新增，
> 不改动原有业务表结构，只新增一张 `Knowledge` 表与一个 `/ai/` 页面。

## 一、模块定位

把大模型当成“一个会写字的接口”：给它文字指令，它返回文字结果。学生侧要做的三件事只有：

1. **封装调用**：`LLMClient.chat(prompt) -> str`，全站唯一入口；
2. **写提示词**：角色 + 要求 + 输出格式；
3. **注入资料**：把数据库里的制度、考勤、薪资转成文本拼进 prompt。

四个功能（JD / 问答 / 点评 / 多轮）都复用同一个 `chat()`，差别只在提示词和“要不要先查库”。

## 二、文件清单

| 任务 | 文件 | 作用 |
| --- | --- | --- |
| T1 | `hrms/settings.py` | 读取 `AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL` 等环境变量 |
| T1 | `app01/utils/ai.py` | `LLMClient`：懒加载客户端、`chat`、`chat_stream`、消息组装、输入清洗、异常翻译 |
| T1 | `scripts/ai_env.ps1` | 方式 A：PowerShell 临时环境变量（Key 由使用者自己填） |
| T1 | `scripts/ai_selftest.py` | 验收脚本：真实调用一次模型并打印回答 / 友好失败提示 |
| T2 | `app01/utils/prompts.py` | 三段式提示词模板（JD / 问答 / 点评 / 对话） |
| T2 | `app01/views/ai.py::generate_jd` | 生成 JD 的 JSON 接口 |
| T3 | `app01/models.py::Knowledge` | 制度知识条目（标题 / 分类 / 内容） |
| T3 | `app01/utils/retrieval.py` | 关键词切分 + SQL 召回 + 打分排序 + 资料拼接 |
| T3 | `app01/views/ai.py::knowledge_qa` | 检索 → 注入 → 回答；无命中直接“不知道” |
| T3 | `app01/management/commands/ai_init.py` | 预置 17 条制度（考勤 / 请假 / 薪资 / 报销 / 人事 / 行政 / 培训 / 福利 / 安全） |
| T4 | `app01/views/ai.py::data_comment` | 聚合某员工某月考勤 + 薪资，转文本后让模型点评 |
| T5 | `app01/views/ai.py::chat` | 多轮对话（前端回传 history，服务端裁剪最近 4 轮） |
| T6 | `app01/utils/ai.py::clean_text`、异常映射 | 输入长度/控制字符过滤、30 秒超时、失败兜底 |
| T7 | `app01/views/ai.py::chat_stream` | SSE 流式输出（`text/event-stream`） |
| 前端 | `app01/templates/ai/index.html` | 四个标签页 + jQuery AJAX + `fetch` 流式渲染 |
| 权限 | `app01/utils/permissions.py` | 新增权限码 `ai:view`，模块前缀 `/ai/` |

## 三、实现要点

### 1. `LLMClient`（T1）

```python
from app01.utils.ai import LLMClient
print(LLMClient.chat("用一句话介绍你自己"))
```

- **配置**：`AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL` 全部来自 `os.environ`，代码里没有 Key；
- **懒加载**：同一进程只建一个 `OpenAI` 客户端，换服务商只改 `AI_BASE_URL`（都兼容 OpenAI 协议）；
- **统一异常**：网络、鉴权、限流、超时、模型名错误都翻译成一句中文提示（`LLMError`），
  视图层直接 `return {"status": false, "error": str(exc)}`，页面不会崩；
- **消息组装**：`build_messages(prompt, system, history)` 把“人设 + 历史 + 本轮问题”排成
  标准 `messages` 列表，历史只保留最近 `AI_HISTORY_TURNS * 2` 条，非法结构直接丢弃。

### 2. 提示词三段式（T2）

`prompts.py` 里每个模板都按“角色 / 要求 / 输出格式”写，例如 JD：

- 角色：资深 HR；
- 要求：贴合岗位、薪资只给区间、不承诺资料外待遇；
- 输出格式：岗位职责 4 条 → 任职要求 4 条 → 薪资范围一行，全文 ≤220 字。

这样写的好处是**输出可预期**：前端拿到的就是能直接展示的三段文字，不用再解析 Markdown。

### 3. 制度问答（T3，简化版 RAG）

流程：

```
问题 → 关键词切分 → SQL 召回（icontains，最多 50 条） → 打分排序（标题 3 分 / 正文 1 分） → top3
     → 拼成【资料】 → 提示词（system 限定“只能依据资料回答”） → 模型回答
```

关键词切分（`extract_keywords`）做了三件事，解决“整句话拿去 LIKE 匹配不到”的问题：

1. 按标点切段并剥掉疑问词（怎么、如何、多少、请问……）；
2. 整段先作为一个关键词（适合“报销标准”这种短问句）；
3. 再做 2 字滑窗（“迟到怎么扣钱” → 迟到 / 到怎 / 怎么 / 么扣 / 扣钱），停用词过滤后剩下的词就能命中制度原文。

**没检索到资料时直接返回“不知道”**：不浪费一次模型调用，也彻底避免模型自由发挥。

### 4. 数据点评（T4）

1. 用 `scope.py` 收窄数据范围（超管全量 / 部门管理员本部门 / 员工本人）；
2. 聚合该员工该月的考勤条数与五种状态次数，取当月薪资记录；
3. 拼成一段可读文本：

```
员工：张伟（技术部），统计月份：2026-11。
考勤：共 20 条记录 —— 按时 16 次、迟到 2 次、早退 1 次、缺勤 1 次、迟到并早退 0 次。
薪资：基本工资 8000.00 元、奖金 500.00 元、扣款 100.00 元、实发 8400.00 元。
```

4. 提示词要求输出“点评：… / 建议：…”两行，`temperature=0.4` 保证客观稳定。

### 5. 多轮对话（T5）

- 浏览器维护 `history`（`{role, content}` 数组），每次请求把**本轮之前**的历史一起回传；
- 服务端 `_load_history` 做三件事：解析 JSON、只保留最近 4 轮、清洗内容；
- 若前端把本轮问题也塞进 history，服务端会把末尾重复的那条去掉，避免同一句出现两次；
- 因此“那如果缺勤呢？”这类追问能接住上文。

### 6. 安全与健壮性（T6）

| 风险 | 措施 |
| --- | --- |
| 超长输入 | `clean_text` 按 `AI_MAX_INPUT`（默认 400 字）截断，前端 `maxlength` 同步限制 |
| 控制字符 / 异常字符 | 正则剔除 `\x00-\x1f`（除常见空白） |
| 网络慢 / 挂死 | `OpenAI(timeout=30, max_retries=1)` |
| Key 错误 / 限流 / 模型名错 | 异常翻译成明确中文提示，HTTP 200 + `status:false` |
| 越权 | `/ai/` 走 RBAC 模块拦截 + `@require_perm("ai:view")`，数据点评再叠加数据范围 |
| Key 泄露 | 只放环境变量；`.gitignore` 已忽略 `.env` 与 `scripts/ai_env.ps1`，仓库里只有占位符模板 `ai_env.example.ps1` |

### 7. 流式输出（T7）

- 后端：`StreamingHttpResponse(content_type="text/event-stream")`，逐条推送
  `data: {"delta": "..."}`，结束发 `{"done": true}`，异常发 `{"error": "..."}`；
- 前端：`fetch` + `ReadableStream` 按 `\n\n` 切包，边收边写进气泡；
- 为什么不用 `EventSource`：它只支持 GET，问题只能塞 URL，长度和编码都别扭；POST + fetch 更稳。
- 关闭代理缓冲：响应头加 `X-Accel-Buffering: no`，否则 Nginx 会攒够一段才发。

## 四、验收步骤

```powershell
cd E:\hrms

# 1) 配置 Key（方式 A，仅当前窗口有效）
notepad .\scripts\ai_env.ps1          # 把占位符替换成真实 Key
. .\scripts\ai_env.ps1

# 2) 建表 + 预置制度 + 权限同步
E:\work_down\python\python.exe manage.py migrate
E:\work_down\python\python.exe manage.py ai_init
E:\work_down\python\python.exe manage.py init_data

# 3) T1 验收：真实调用一次
E:\work_down\python\python.exe scripts\ai_selftest.py
E:\work_down\python\python.exe scripts\ai_selftest.py --stream "写一句上班提醒"

# 4) 单元测试（AI 部分用 mock，不联网）
E:\work_down\python\python.exe manage.py test app01

# 5) 启动
$env:HRMS_DEBUG = "1"
E:\work_down\python\python.exe manage.py runserver 127.0.0.1:8000
```

浏览器打开 <http://127.0.0.1:8000/ai/>，逐项演示：

| 步骤 | 操作 | 预期 |
| --- | --- | --- |
| T2 | 岗位名称填「Java 后端工程师」，点“生成 JD” | 返回含“岗位职责 / 任职要求 / 薪资范围”三段 |
| T3 | 问“迟到怎么扣钱？” | 返回制度原文口径，下方标签显示命中的《迟到、早退与缺勤的处理》等 |
| T3 | 问“年会抽奖怎么报名？” | 回答“不知道”，并提示联系人事部门 |
| T4 | 选员工 + 月份，点“生成点评” | 返回“点评：… / 建议：…”两行，下方显示注入的数据文本 |
| T5 | 问“迟到怎么算？”→“那如果缺勤呢？” | 第二问能接上文，不会答非所问 |
| T7 | 勾选“流式输出”再提问 | 文字逐词出现 |

> 实测记录（2026-11-16，`Qwen/Qwen2.5-7B-Instruct`）：T2 3.9 s、T3 2.8 s（无命中 0 s）、T4 1.2 s、T5 1.8 s、T7 1.5 s（35 个 SSE 事件），
> 输出结构符合提示词要求；详见 `docs/self-test-record.md` 第六节。

> **脚本编码**：`scripts/ai_env.ps1` 必须保存为 UTF-8 **带 BOM**。Windows PowerShell 5.1 读无 BOM 的 UTF-8 会按 GBK 解码，
> 中文乱码并报 `数组索引表达式丢失或无效`；模板见 `scripts/ai_env.example.ps1`（已入库，含占位符）。

## 五、常见提问与标准答法

1. **为什么不直接把整段问题拿去 SQL 匹配？**
   中文没有空格分词，整句 `icontains` 往往匹配不到；切关键词 + 2 字滑窗能在不引入分词库的前提下覆盖绝大多数问法。
2. **模型会不会瞎编制度？**
   两道锁：system 明确“只能依据资料，资料没有就说不知道”，并且检索不到资料时**根本不调用模型**，直接返回“不知道”。
3. **为什么把 Key 放环境变量？**
   Key 属于凭据，写进代码会随 Git 泄露；放环境变量后代码可公开、Key 只存在本机，换 Key 不用改代码。
4. **temperature 为什么各模块不一样？**
   问答 / 点评要稳定（0.2 / 0.4），JD 与闲聊可以有点变化（0.6）。
5. **多轮对话历史存在哪里？**
   存在浏览器内存，每次请求回传；服务端只保留最近 4 轮。这样无需引入 Redis/数据库，刷新页面即重置。
6. **流式输出失败了怎么办？**
   前端捕获异常后把错误写进气泡；非流式接口仍然可用，勾掉“流式输出”即可。
7. **怎么换模型 / 换服务商？**
   只改环境变量：`AI_BASE_URL` + `AI_MODEL`（DeepSeek、通义、GLM 都提供 OpenAI 兼容接口），代码零改动。

## 六、已知限制

1. 无网络或 Key 失效时，AI 功能只返回友好提示，不会生成内容；答辩前先跑 `ai_selftest.py`。
2. 知识库是关键词召回，不是向量检索；问法太抽象可能召回不到，需要补充 `ai_init.py` 里的条目。
3. 未做用量统计与限流（`LLMClient` 是唯一入口，后续可在 `chat()` 里加计数与配额）。
4. 制度条目内容为本项目自拟的示例文本，**上线前需替换为公司真实制度**，否则回答的依据不成立。
