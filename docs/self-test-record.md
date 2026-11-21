# HRMS 模块自测记录表

- 项目：企业员工管理系统（HRMS）
- 环境：Windows / Python 3.12.5（`E:\work_down\python\python.exe`）/ Django 5.0.14 / MySQL 8.0.45 / mysqlclient 2.3.0 / Pillow 11.2.1
- 自测日期：2026-11-06
- 自测方式：`manage.py check`、`manage.py test app01`（34 个单元测试用例）、`scripts/smoke_check.py`（33 个地址）、真实 `runserver` + HTTP 请求验证静态资源

## 一、总体结果

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 配置静态检查 | `E:\work_down\python\python.exe manage.py check` | 通过，`System check identified no issues (0 silenced).` |
| 单元测试 | `E:\work_down\python\python.exe manage.py test app01` | 通过，`Ran 34 tests in 21s OK` |
| 页面冒烟 | `E:\work_down\python\python.exe scripts\smoke_check.py` | 通过，33 个地址，失败 0 个 |
| 静态资源 | HTTP GET | `/static/css/site.css`、Bootstrap、jQuery、ECharts、datepicker、`/image/code/` 均 200 |
| 首页渲染 | HTTP GET `/` | 200，`|money` 过滤器已加载 |

## 二、分模块自测

| 模块 | 用例 / 检查点 | 结论 |
| --- | --- | --- |
| 登录与认证（T4） | 登录页可访问且含验证码；验证码错误拦截；验证码正确（忽略大小写）登录成功；密码为 PBKDF2 哈希；未登录访问受保护页面 302 到 `/login/` | 通过 |
| 部门管理（T2） | 新增部门；重复名称被拒（“该部门已存在”）；有员工时删除被保护并提示；空部门可删除 | 通过 |
| 员工管理（T3） | 列表加载；新增成功；手机号格式非法被拒；手机号重复被拒；年龄越界被拒；编辑自身不误判手机号重复；搜索与部门筛选生效；删除成功 | 通过 |
| 考勤管理（T6） | 按时 / 迟到 / 早退 / 缺勤 / 迟到并早退 五种状态自动判定；列表可展示状态标签 | 通过 |
| 薪资管理（T7） | 新增后实发自动等于 底薪+奖金-扣款；按月份筛选后总额统计正确（9,000.00） | 通过 |
| 权限控制（T5） | 普通员工访问员工模块 403；普通员工可访问 `/my/profile/`；部门管理员可查看员工；部门管理员无删除权限时 403；AJAX 越权返回 `{"status": false, "error": "您没有访问该模块的权限"}` | 通过 |
| AJAX 任务（T9） | 合法数据返回 `{"status": true, "data": {...}}`；非法数据返回 HTTP 400 + 字段级错误 JSON | 通过 |
| 统计图表（T10） | `/stats/` 页面 200；`/stats/depart-chart/`、`/stats/salary-trend/`、`/stats/attendance-chart/` 三个 JSON 接口 200 | 通过 |
| 系统管理 | 用户列表 / 新增 / 编辑、角色列表 / 新增 / 编辑、权限清单页面 200 | 通过 |
| 公告 | 列表 / 新增 / 编辑 / 详情页面 200 | 通过 |
| 员工自助 | `staff` 账号访问 `/my/profile/`、`/my/attendance/`、`/my/salary/` 均 200 | 通过 |
| 演示数据补充命令 | `add_people --count 3`：新增 3 人、手机号互不重复、每人 2 天考勤 + 2 个月薪资且实发金额自洽；`--people-only` 只加人不加记录 | 通过 |

## 三、自测发现并修复的问题

| # | 问题 | 原因 | 处理 |
| --- | --- | --- | --- |
| 1 | 薪资统计报 `FieldError: 'total' is an aggregate` | `aggregate(total=Sum("total"))` 的别名与字段同名，`Avg("total")` 被解析成聚合套聚合 | 统计别名改为 `sum_total` / `avg_total`，模板同步修改 |
| 2 | 薪资趋势接口 500 | 同类问题：`annotate(total=Sum("total"), avg=Avg("total"))` | 改为 `sum_total` / `avg_total` |
| 3 | 首页 500：`Invalid filter: 'money'` | `index.html` 使用 `|money` 但未 `{% load rbac_tags %}` | 模板补充 `{% load rbac_tags %}` |
| 4 | 冒烟脚本 33 个地址全部 400 | 脚本走真实 settings，`testserver` 不在 `ALLOWED_HOSTS` | 脚本 `django.setup()` 后追加 `testserver` |
| 5 | 切换到全局解释器后 `makemigrations --check` 提示模型漂移 | 此前为年龄字段补了自定义校验消息，未生成迁移 | 生成 `app01/migrations/0002_alter_employee_age.py` 并 `migrate` |
| 6 | 全局解释器缺少 `pymysql`，`manage.py check` 直接报 `ModuleNotFoundError` | `hrms/__init__.py` 硬性 `import pymysql`，而该环境装的是 mysqlclient | 改为「优先 PyMySQL，缺失则回退 MySQLdb」，两种驱动均可运行 |
| 7 | 页面完全没有样式：输入框是浏览器默认样式、侧边栏变成项目符号列表 | `DEBUG=False` 时 Django 的 `runserver` 不托管静态文件，`/static/css/site.css` 返回 500 | 启动前设 `HRMS_DEBUG=1` 环境变量；或 `runserver --insecure` 临时托管静态文件 |
| 8 | 首页日期显示成「2026年十一月月星期五日」 | 模板用了 `date:"Y年M月D日"`，`M` 是月份名、`D` 是星期名，与字面「月/日」重复 | 改为 `date:"Y年m月d日"`，输出「2026年11月06日」 |

## 三之二、数据规模（补充演示数据后）

| 数据 | 数量 |
| --- | --- |
| 部门 | 4 |
| 员工 | 52（原有 12 + `add_people` 新增 40） |
| 考勤 | 864 条（状态分布：按时 468 / 迟到 149 / 早退 109 / 缺勤 91 / 迟到并早退 47） |
| 薪资 | 192 条（合计实发 ￥2,052,400.00） |
| 账号 | 3（admin / deptmgr / staff） |

## 四、未覆盖 / 需人工确认

1. **真实浏览器界面检查**：本次只到 HTML / HTTP 层，未逐页人工点检视觉效果（配色、表格宽度、移动端折叠）。
2. **ECharts 实际渲染**：接口已返回正确 JSON，图表是否出现需在浏览器中打开 `/stats/` 确认（依赖 `HRMS_DEBUG=1` 才能加载 `echarts.min.js`）。
3. **头像上传回显**：表单校验已覆盖类型与大小，但真实图片文件上传的落盘与展示建议手工走一次。
4. **验证码可读性**：PIL 生成，字体依赖系统字体，建议在浏览器中确认是否清晰。
5. **并发与大数据量**：单元测试为小数据量，未做 10 万级员工压测。

## 五、复现步骤

```powershell
cd E:\hrms
E:\work_down\python\python.exe manage.py check
E:\work_down\python\python.exe manage.py test app01
E:\work_down\python\python.exe scripts\smoke_check.py
```

---

## 六、AI 智能助手自测（2026-11-16）

- 环境：同上（Python 3.12.5 / Django 5.0.14 / MySQL 8.0.45），新增 `openai 3.51.0`
- 变更：新增 `Knowledge` 表（迁移 `0003_knowledge.py`）、权限码 `ai:view`（共 27 项）、路由 `/ai/`

### 1. 总体结果

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 静态检查 | `manage.py check` | 通过，`System check identified no issues (0 silenced).` |
| 迁移 | `manage.py migrate` | `Applying app01.0003_knowledge... OK` |
| 知识库预置 | `manage.py ai_init` | 新增 17 条，当前共 17 条 |
| 权限同步 | `manage.py init_data` | 权限 27 项（新增 `ai:view` 1 项），角色 3 个同步完成 |
| 单元测试 | `manage.py test app01` | 通过，`Ran 50 tests in 23.0s OK`（新增 16 个 AI 用例） |
| 页面冒烟 | `scripts/smoke_check.py` | 通过，34 个地址，失败 0 个（含 `/ai/`） |
| T1 自检（未配置 Key） | `scripts/ai_selftest.py` | 按设计返回友好提示「尚未配置 AI_API_KEY…」，不抛栈、页面不崩 |
| T1 自检（已配置 Key） | `scripts/ai_selftest.py` | 通过：真实返回模型回答（Qwen2.5-7B-Instruct 耗时 2.8 秒；DeepSeek-R1-0528 同样通过，耗时 17.0 秒） |

### 2. 检索召回自测（`app01/utils/retrieval.py`）

| 问题 | 切出的关键词（前 6 个） | 命中条目 |
| --- | --- | --- |
| 迟到怎么扣钱？ | 迟到扣钱 / 迟到 / 到扣 / 扣钱 | 迟到、早退与缺勤的处理；标准工作时间与打卡要求 |
| 报销标准是多少 | 报销标准 / 报销 / 销标 / 标准 | 差旅报销标准；标准工作时间与打卡要求；费用报销制度 |
| 年假有几天 | 年假 | 年假规定 |
| 忘记打卡怎么办 | 忘记打卡 / 忘记 / 记打 / 打卡 | 忘记打卡与补卡流程；标准工作时间与打卡要求 |
| 加班费怎么算 | 加班费算 / 加班 / 班费 / 费算 | 加班与调休 |
| 年会抽奖 | 年会抽奖 / 年会 / 会抽 / 抽奖 | 无命中 → 按设计回答“不知道” |

### 3. AI 单元测试覆盖点（mock 模型调用，不联网、不需要真实 Key）

| 用例 | 覆盖 |
| --- | --- |
| `test_page_shows_unconfigured_notice` | 未配置 Key 时页面给出提示，而不是报错 |
| `test_staff_without_ai_permission_denied` | 无 `ai:view` 权限访问 `/ai/` 返回 403 |
| `test_jd_requires_title` / `test_jd_success` | JD 参数校验、提示词包含岗位与部门 |
| `test_llm_failure_returns_friendly_error` | 模型抛错时返回友好 JSON，HTTP 200、`status:false` |
| `test_qa_without_knowledge_returns_unknown` | 无命中直接返回“不知道”，且 `sources` 为空 |
| `test_qa_with_knowledge_injects_context` | 命中条目被拼进提示词（含《标题》），并回传来源 |
| `test_comment_injects_attendance_and_salary` | 考勤/薪资文本（“迟到 1 次”“实发 8400.00 元”）被注入提示词 |
| `test_comment_without_records` | 无数据时返回 400 与友好提示 |
| `test_chat_passes_history_and_drops_duplicate` | 历史传给模型、末尾重复的本轮问题被去掉 |
| `test_chat_input_is_truncated` | `AI_MAX_INPUT=10` 时输入被截断到 10 字 |
| `test_stream_returns_sse_events` | SSE 返回 `text/event-stream`，含 `delta` 与 `done` 事件 |
| `AIClientUnitTests.*` | `clean_text` 截断/去控制字符、messages 只保留最近 N 轮、未配置 Key 抛 `LLMError`、关键词过滤停用词 |

### 4. 真实链路验证（硅基流动 · `Qwen/Qwen2.5-7B-Instruct`）

| 接口 | 输入 | 结果 | 耗时 |
| --- | --- | --- | --- |
| T2 JD | 岗位「Java 后端工程师」/ 部门「技术部」 | 返回“岗位职责 4 条 + 任职要求 4 条 + 薪资范围 12-18K”三段齐全 | 3.9 s |
| T3 问答（命中） | 迟到怎么扣钱？ | 引用《迟到、早退与缺勤的处理》作答；`sources` 命中 2 条（迟到处理、打卡要求） | 2.8 s |
| T3 问答（未命中） | 年会抽奖怎么报名？ | 直接返回“不知道” + hint，`sources` 为空，未调用模型 | 0.0 s |
| T4 点评 | 张伟 / 2026-11 | 输出“点评：按时 4 次、迟到 1 次、早退 1 次、扣款 500 元”“建议：调整时间管理…”；`data_text` 注入正确（实发 11500.00 元） | 1.2 s |
| T5 对话 | 你好，用两句话介绍你能帮我做什么 | 正常回答，`history_used=0` | 1.8 s |
| T7 SSE | 用一句话说明迟到会怎么处理 | `text/event-stream`，35 个事件（start + 32 delta + done），逐词推送 | 1.5 s |

结论：真实调用链路可用。同为 8B 级模型，`DeepSeek-R1-0528-Qwen3-8B` 单次约 17 秒且思考过程不会出现在 `delta` 里
（流式会长时间空白），演示建议用 `Qwen2.5-7B-Instruct`。

### 5. 未覆盖 / 需人工确认

1. **浏览器交互**：页面已用渲染预览截图检查四个标签页布局；按钮点击后的实际动画/滚动建议在
   Chrome / Edge 中演示一遍（需 `HRMS_DEBUG=1`）。
2. **知识库文本真实性**：17 条制度为本项目自拟示例，交付前需替换为公司真实制度。
3. **Key 保管**：`scripts/ai_env.ps1` 现含真实 Key，已加入 `.gitignore`；提交作业/截图时不要把该文件内容露出。

