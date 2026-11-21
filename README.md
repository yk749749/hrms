# HRMS 企业员工管理系统

基于 **Django 5.2 + MySQL 8 + Bootstrap 3.4.1 + jQuery 3.6.0 + ECharts 5** 的企业员工管理系统，是《企业员工管理系统》课程设计的完整实现。项目在既有「联通用户管理系统」(`E:\ems`) 的工程结构基础上重构业务，覆盖部门、员工、考勤、薪资、公告、任务、统计分析与系统管理（RBAC）等模块，并包含环境搭建、数据初始化、单元测试与安全加固等工程化内容。

在此之上新增 **AI 智能助手** 模块（对应《基于大模型的智能员工助手课程设计任务书》T1–T7）：招聘 JD 生成、制度知识库问答（简化版 RAG）、考勤/薪资数据智能点评、多轮对话与 SSE 流式输出，全部复用同一套 `LLMClient`。

---

## 目录

- [一、技术栈](#一技术栈)
- [二、目录结构](#二目录结构)
- [三、数据模型（ER 说明）](#三数据模型er-说明)
- [四、RBAC 权限设计](#四rbac-权限设计)
- [五、功能清单（对照任务书）](#五功能清单对照任务书)
- [六、快速开始](#六快速开始)
- [七、路由表](#七路由表)
- [八、关键实现说明](#八关键实现说明)
- [九、自测与验证](#九自测与验证)
- [十、安全配置（T13）](#十安全配置t13)
- [十一、已知限制与后续可做](#十一已知限制与后续可做)
- [十二、常见问题](#十二常见问题)

---

## 一、技术栈

| 分类 | 技术 / 版本 |
| --- | --- |
| 开发语言 | Python 3.12.5（解释器 `E:\work_down\python\python.exe`） |
| Web 框架 | Django 5.2.x（任务书要求）；本机全局环境实装 Django 5.0.14，项目已在 5.0.14 下通过全部检查与 50 个单元测试 |
| 数据库 | MySQL 8.0.45（`hrms` 库，utf8mb4，`STRICT_TRANS_TABLES`） |
| 数据库驱动 | mysqlclient 2.3.0（本机实装）；`hrms/__init__.py` 会自动优先适配 PyMySQL，两者任装其一即可 |
| 前端框架 | Bootstrap 3.4.1 |
| 前端库 | jQuery 3.6.0、ECharts 5（本地静态文件，不依赖 CDN） |
| 图片处理 | Pillow 11.2.1（登录图形验证码、员工头像校验） |
| 大模型服务 | 硅基流动 SiliconFlow（OpenAI 兼容接口），默认模型 `Qwen/Qwen2.5-7B-Instruct`；换服务商只改 `AI_BASE_URL` |
| 大模型 SDK | `openai`（Python SDK）。`AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL` 全部走环境变量，不进代码、不进 Git |
| 认证与权限 | Django `AbstractUser` 自定义用户模型 + 自建 RBAC（角色 / 权限码） |

---

## 二、目录结构

```
hrms/
├── manage.py
├── requirements.txt
├── .gitignore
├── README.md
├── docs/
│   ├── AI模块说明.md                # AI 模块（T1–T7）设计说明与验收步骤
│   └── self-test-record.md          # 模块自测记录表
├── scripts/
│   ├── ai_env.ps1                   # 方式 A：PowerShell 临时环境变量（含本机 Key，已 .gitignore）
│   ├── ai_env.example.ps1           # 同上的模板（占位符，可入库/提交）
│   ├── ai_selftest.py               # T1 验收：调用一次模型并打印回答
│   └── smoke_check.py               # 页面冒烟检查脚本
├── logs/                            # 运行日志（自动创建）
│   ├── hrms.log                     # INFO 及以上
│   ├── error.log                    # ERROR 及以上
│   └── security.log                 # 权限拒绝 / 登录失败
├── hrms/                            # 配置包
│   ├── __init__.py                  # 数据库驱动适配（PyMySQL 优先，兼容 mysqlclient）
│   ├── settings.py                  # 数据库 / 中文 / 时区 / 日志 / 安全头
│   ├── urls.py                      # 全局路由表
│   ├── wsgi.py / asgi.py
├── app01/                           # 业务应用
│   ├── models.py                    # 10 个模型（用户、RBAC、业务、知识库）
│   ├── forms.py                     # 11 个表单类（统一继承 utils/bootstrap.py 的样式基类）
│   ├── tests.py                     # 50 个单元测试用例
│   ├── admin.py                     # 全部模型注册后台
│   ├── views.py                     # 兼容占位（真实视图在 views/ 包）
│   ├── views/                       # 按模块拆分的视图包
│   │   ├── __init__.py              # 统一导出，urls.py 只从这里取视图
│   │   ├── account.py               # 登录 / 注销 / 图形验证码
│   │   ├── home.py                  # 首页看板
│   │   ├── depart.py                # 部门管理
│   │   ├── employee.py              # 员工管理（含详情、头像）
│   │   ├── attendance.py            # 考勤管理
│   │   ├── salary.py                # 薪资管理
│   │   ├── announcement.py          # 公告管理
│   │   ├── task.py                  # 任务管理（AJAX）
│   │   ├── stats.py                 # 统计分析与 3 个图表 JSON 接口
│   │   ├── system.py                # 用户 / 角色 / 权限管理
│   │   ├── my.py                    # 员工自助（个人 / 考勤 / 薪资）
│   │   └── ai.py                    # AI 智能助手（JD / 问答 / 点评 / 多轮 / SSE）
│   ├── middleware/
│   │   ├── auth.py                  # 登录拦截
│   │   └── rbac.py                  # 模块级权限拦截
│   ├── utils/
│   │   ├── ai.py                    # LLMClient 统一封装（chat / chat_stream / 异常友好化）
│   │   ├── prompts.py               # 三段式提示词模板（角色 + 要求 + 输出格式）
│   │   ├── retrieval.py             # 知识库关键词检索 + 打分（简化版 RAG 的“检索”）
│   │   ├── bootstrap.py             # BootstrapModelForm：统一给控件加 form-control
│   │   ├── pagination.py            # 分页器（深拷贝 request.GET 保留查询条件）
│   │   ├── code.py                  # PIL 图形验证码
│   │   ├── permissions.py           # 权限清单 / 角色定义 / URL 前缀→模块映射（唯一来源）
│   │   ├── decorators.py            # @require_perm 接口级权限装饰器
│   │   ├── context_processors.py    # 模板可用的 perms_codes / 菜单
│   │   └── scope.py                 # 数据范围收窄（超管 / 部门管理员 / 普通员工）
│   ├── templatetags/
│   │   └── rbac_tags.py             # has_perm / money / status_class / level_class / percent
│   ├── management/commands/
│   │   ├── init_data.py             # 权限 + 角色 + 超级管理员
│   │   ├── ai_init.py               # 预置制度知识库条目（17 条，幂等）
│   │   ├── demo_data.py             # 演示业务数据（支持 --force）
│   │   └── add_people.py            # 增量批量补员工 + 考勤 + 薪资
│   ├── migrations/                  # 0001 建表与约束，0002 调整年龄校验器，0003 新增 Knowledge 表
│   ├── templates/                   # 母版 + 各模块模板
│   └── static/                      # Bootstrap / jQuery / ECharts / 自定义样式
```

---

## 三、数据模型（ER 说明）

| 模型 | 关键字段 | 说明 |
| --- | --- | --- |
| `Permission` | `code`（唯一，格式 `模块:动作`）、`name`、`module` | 权限最小单元，共 27 项 |
| `Role` | `name`、`code`、`permissions`(M2M) | 角色，内置 3 个：超管 / 部门管理员 / 普通员工 |
| `User` | 继承 `AbstractUser`；`real_name`、`phone`、`department`(FK)、`employee`(O2O→Employee)、`roles`(M2M) | 自定义用户模型，`AUTH_USER_MODEL = "app01.User"` |
| `Department` | `title`（唯一）、`note` | 部门；被员工外键 `PROTECT` 保护 |
| `Employee` | `name`、`age`、`gender`、`mobile`（唯一）、`account`（余额）、`create_time`、`depart`(FK)、`avatar`、`is_active` | 员工档案 |
| `Attendance` | `employee`、`date`、`check_in`、`check_out`、`status` | 考勤；`UniqueConstraint(employee, date)` |
| `Salary` | `employee`、`month`（`YYYY-MM`）、`base_salary`、`bonus`、`deduction`、`total` | 薪资；`UniqueConstraint(employee, month)` |
| `Announcement` | `title`、`content`、`is_top`、`create_time`、`author` | 公告，支持置顶 |
| `Task` | `title`、`detail`、`level`(1 紧急/2 重要/3 普通)、`leader`(FK Employee)、`is_done`、`create_time` | 工作任务，AJAX 增改 |
| `Knowledge` | `title`、`category`、`content`、`create_time`、`update_time` | AI 制度知识库，供问答检索后注入提示词（17 条预置） |

关系概览：

```
Department 1 ── n Employee 1 ── n Attendance
                        │  └── n Salary
                        └── 1 User（employee 反向 login_account）

User n ── n Role n ── n Permission
User n ── 1 Department（部门管理员的数据范围依据）
Announcement / Task 独立表，Task.leader → Employee
```

---

## 四、RBAC 权限设计

权限码统一在 `app01/utils/permissions.py` 中定义，**中间件、装饰器、模板上下文、初始化命令都只消费这一份清单**，避免多处维护不一致。

| 模块 | 权限码 |
| --- | --- |
| 部门 | `depart:view` / `depart:add` / `depart:edit` / `depart:delete` |
| 员工 | `employee:view` / `employee:add` / `employee:edit` / `employee:delete` |
| 考勤 | `attendance:view` / `attendance:add` / `attendance:edit` / `attendance:delete` |
| 薪资 | `salary:view` / `salary:add` / `salary:edit` / `salary:delete` |
| 公告 | `announcement:view` / `announcement:add` / `announcement:edit` / `announcement:delete` |
| 任务 | `task:view` / `task:add` |
| 统计 | `stats:view` |
| 智能助手 | `ai:view` |
| 系统 | `system:view` / `system:manage` |
| 自助 | `self:view` |

内置角色绑定：

| 角色 | 权限 |
| --- | --- |
| 超级管理员 `superadmin` | 全部 27 项，且 `is_superuser` 直接放行 |
| 部门管理员 `dept_manager` | 20 项（除系统管理外，业务模块可增删改查） |
| 普通员工 `staff` | 3 项：`self:view`、`announcement:view`、`ai:view` |

三层拦截链：

1. `AuthMiddleware`：未登录跳转 `/login/?next=...`；AJAX 请求返回 `401` + `{"status": false}`。
2. `PermissionMiddleware`：按 `MODULE_URL_PREFIX` 把 URL 归到模块，用户没有任何 `模块:*` 权限则 `403`，并写入 `hrms.security` 日志。
3. `@require_perm("code")`：接口级细校验（如「能看员工列表」不等于「能删除员工」），超管放行，AJAX 返回 `{"status": false, "error": "您没有该操作的权限"}`。

前端按钮显隐使用上下文 `perms_codes`：

```django
{% if 'employee:add' in perms_codes %}
  <a class="btn btn-primary" href="/employee/add/">新增员工</a>
{% endif %}
```

数据范围（`app01/utils/scope.py`）：超管看全量；部门管理员按 `department` 收窄；普通员工只看自己关联的 `employee` 数据。

---

## 五、功能清单（对照任务书）

| 编号 | 功能 | 实现位置 | 状态 |
| --- | --- | --- | --- |
| T1 | 开发环境搭建（项目骨架、依赖、MySQL、静态资源） | `hrms/settings.py`、`requirements.txt`、`app01/static/` | 完成 |
| T2 | 部门管理 CRUD + 分页 + 有员工时禁止删除 | `views/depart.py`、`templates/depart/` | 完成 |
| T3 | 员工管理 CRUD + 搜索 + 筛选 + 分页 + 头像 + 校验 | `views/employee.py`、`forms.py` | 完成 |
| T4 | 登录 / 注销 / 图形验证码 / `next` 安全跳转 | `views/account.py`、`utils/code.py` | 完成 |
| T5 | RBAC 权限控制（中间件 + 装饰器 + 模板显隐 + 数据范围） | `middleware/`、`utils/permissions.py`、`scope.py` | 完成 |
| T6 | 考勤管理，状态按上下班时间自动判定 | `models.Attendance.compute_status()` | 完成 |
| T7 | 薪资管理，实发金额自动计算 + 月度统计 | `models.Salary.compute_total()`、`views/salary.py` | 完成 |
| T8 | 公告管理（置顶、详情、增删改查） | `views/announcement.py` | 完成 |
| T9 | AJAX 任务管理（提交、校验回显、完成状态切换） | `views/task.py`、`templates/task/list.html` | 完成 |
| T10 | ECharts 可视化（部门人数饼图、薪资趋势、考勤分布） | `views/stats.py`、`templates/stats/index.html` | 完成 |
| T11 | ORM 性能优化（`select_related` / `prefetch_related` / `annotate`） | 各列表视图 | 完成 |
| T12 | 单元测试（50 个用例，覆盖 10 个测试类，含 AI 模块 16 个） | `app01/tests.py` | 完成 |
| T13 | 安全加固（CSRF / XSS / 密码哈希 / 安全响应头 / 日志 / 上传校验） | `settings.py`、`forms.py`、`middleware/` | 完成 |

### AI 智能助手（任务书 T1–T7）

| 编号 | 任务 | 实现位置 | 状态 |
| --- | --- | --- | --- |
| T1 | 环境与 `LLMClient` 封装 | `app01/utils/ai.py`、`hrms/settings.py` 的 AI 配置、`scripts/ai_env.ps1`、`scripts/ai_selftest.py` | 完成 |
| T2 | 智能生成招聘 JD | `views/ai.py::generate_jd`、`utils/prompts.py::build_jd_prompt`、`templates/ai/index.html` | 完成 |
| T3 | 制度知识库问答 | `models.Knowledge`、`utils/retrieval.py`、`views/ai.py::knowledge_qa`、`manage.py ai_init` | 完成 |
| T4 | 数据智能点评 | `views/ai.py::data_comment`（先把考勤 + 薪资聚合成文本，再注入提示词） | 完成 |
| T5 | 多轮对话助手 | `views/ai.py::chat` + `LLMClient.build_messages`（保留最近 4 轮） | 完成（选做） |
| T6 | 安全与健壮性 | `LLMClient.clean_text`（长度/控制字符过滤）、超时 + 异常友好化、`AI_MAX_INPUT` 截断 | 完成（选做） |
| T7 | 流式输出（SSE） | `LLMClient.chat_stream` + `views/ai.py::chat_stream` + 前端 `fetch` 流式渲染 | 完成（选做） |

实现思路只有三步：**① 封装调用（`LLMClient`）→ ② 写提示词（三段式）→ ③ 注入资料（把检索结果 / 数据转成文本塞进 prompt）**。
四个功能复用同一个 `chat()`，差别只在提示词和“要不要先查库”。

AI 模块纳入 RBAC：新增权限码 `ai:view`（模块前缀 `/ai/`），超级管理员与部门管理员、普通员工均可用；
数据点评的数据范围仍由 `utils/scope.py` 收窄——普通员工只能点评自己的数据。

### 业务规则

- 考勤：标准上班 `09:00`、下班 `18:00`。两次打卡都缺或只打一次 → 缺勤(4)；上班晚于 09:00 → 迟到(2)；下班早于 18:00 → 早退(3)；两者都触发 → 迟到并早退(5)；其余为按时(1)。`status` 不在表单中出现，由 `save()` 兜底计算。
- 薪资：`total = base_salary + bonus - deduction`，同样由 `save()` 兜底；列表支持按月份筛选并展示总额 / 人均 / 最高 / 最低 / 人数。
- 员工校验：姓名 2–16 字；年龄 18–65；手机号 `^1[3-9]\d{9}$` 且唯一（编辑时排除自身）；余额非负；头像 ≤ 2MB 且限 jpg/png/gif/webp。
- 部门：`title` 唯一；`Employee.depart` 使用 `PROTECT`，删除有员工的部门时捕获 `ProtectedError` 并提示。

---

## 六、快速开始

### 1. 使用本机解释器（无需虚拟环境）

项目直接用本机 Python 3.12 运行，解释器路径固定为：

```text
E:\work_down\python\python.exe        # Python 3.12.5，已装 Django / mysqlclient / Pillow
```

确认依赖是否齐全（本项目当前环境已满足）：

```powershell
E:\work_down\python\python.exe -c "import django, MySQLdb, PIL; print(django.get_version())"
```

如果换了一台机器，先装依赖：

```powershell
E:\work_down\python\python.exe -m pip install -r requirements.txt
```

> 说明：`requirements.txt` 按任务书要求写的是 `Django>=5.2,<5.3`；本机实装的是 Django 5.0.14，项目在该版本下同样通过全部检查与测试。若要严格对齐任务书版本，执行 `E:\work_down\python\python.exe -m pip install "Django>=5.2,<5.3"` 即可（这会升级该解释器下的全局 Django，请注意同机其他 Django 项目）。

### 2. 准备数据库

在 MySQL 中创建库（默认连接参数见 `hrms/settings.py`，可用环境变量覆盖）：

| 环境变量 | 默认值 |
| --- | --- |
| `HRMS_DB_NAME` | `hrms` |
| `HRMS_DB_USER` | `root` |
| `HRMS_DB_PASSWORD` | `123456` |
| `HRMS_DB_HOST` / `HRMS_DB_PORT` | `127.0.0.1` / `3306` |

```sql
CREATE DATABASE IF NOT EXISTS hrms DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

本机 mysql 客户端在 `E:\MySQL\mysql-8.0.45-winx64\bin\mysql.exe`，可直接建库：

```powershell
& "E:\MySQL\mysql-8.0.45-winx64\bin\mysql.exe" --user=root --password=123456 --host=127.0.0.1 --port=3306 `
  -e "CREATE DATABASE IF NOT EXISTS hrms DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
```

### 3. 迁移与初始化

```powershell
cd E:\hrms
E:\work_down\python\python.exe manage.py migrate
E:\work_down\python\python.exe manage.py init_data          # 权限 27 项 + 角色 3 个 + 超管
E:\work_down\python\python.exe manage.py ai_init           # AI 制度知识库 17 条（幂等）
E:\work_down\python\python.exe manage.py demo_data --force  # 可选：演示业务数据
E:\work_down\python\python.exe manage.py add_people         # 可选：再批量补 40 人 + 考勤 + 薪资
```

`init_data` 可重复执行（幂等）；`demo_data` 会先清空部门 / 员工 / 考勤 / 薪资 / 公告 / 任务，再重建演示数据。

`add_people` 是**增量**命令（不清空任何数据），常用参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--count` | 40 | 新增员工数量；手机号从 `13900000001` 起顺延，自动跳过已占用号码 |
| `--days` | 15 | 为每位新员工生成最近多少个工作日的考勤 |
| `--months` | 3 | 为每位新员工生成最近几个月的薪资 |
| `--people-only` | 关闭 | 只加员工，不生成考勤与薪资 |

例：`manage.py add_people --count 10 --days 0 --months 0`（只补 10 个人）。

### 4. 配置大模型（方式 A：PowerShell 临时环境变量）

本项目按任务书要求采用 **方式 A**：只在当前 PowerShell 窗口有效，关窗口即失效。

1. 编辑 `scripts/ai_env.ps1`，把 `AI_API_KEY` 的占位符换成真实 Key
   （硅基流动控制台 <https://cloud.siliconflow.cn> 申请；模型名从「模型广场」复制，含“组织/”前缀，如 `Qwen/Qwen2.5-7B-Instruct`）；
   若该文件已被删/被覆盖，用模板重建：`Copy-Item .\scripts\ai_env.example.ps1 .\scripts\ai_env.ps1`；
2. 在**将用来启动服务的同一个窗口**执行（开头有一个点 `.`，表示在当前窗口生效；不加点变量会随子进程退出而丢失）：

```powershell
cd E:\hrms
. .\scripts\ai_env.ps1
```

3. 验证配置与调用（T1 完成标志）：

```powershell
E:\work_down\python\python.exe scripts\ai_selftest.py
```

返回模型回答即为通过；若提示 `尚未配置 AI_API_KEY`，说明脚本没有“点执行”，或 Key 仍是占位符。
首页 `/ai/` 右上角也会显示「已连接：模型名」或「未配置 API Key」。

> 方式 B（永久生效）：`[Environment]::SetEnvironmentVariable("AI_API_KEY", "你的Key", "User")`，重开终端后生效。
> Key 只写在本机环境变量里，不要写进代码或提交 Git。

> **编码坑（Windows PowerShell 5.1）**：`ai_env.ps1` 必须保存为 **UTF-8 带 BOM**。
> 无 BOM 的 UTF-8 会被 5.1 按 GBK 解码，中文全部乱码并报 `数组索引表达式丢失或无效`，脚本根本执行不完。
> 用记事本/VS Code 改过该文件后请确认编码仍是 `UTF-8 with BOM`；`scripts/ai_env.ps1` 已加入 `.gitignore`（含本机 Key，不入库）。

### 5. 启动

启动分两步：先起 MySQL 服务端，再起 Django。全部手动，不依赖任何脚本。

**第一步：确认 MySQL 是否已在运行**

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 3306
```

有输出（`:: 3306 Listen`）说明库已经在跑，直接跳到第二步。没有输出说明库没起，用下面这条把它拉起来：

```powershell
& "E:\MySQL\mysql-8.0.45-winx64\bin\mysqld.exe" --defaults-file=E:\MySQL\mysql-8.0.45-winx64\my.ini --console
```

- `--defaults-file` 必须带，否则 mysqld 找不到 `my.ini`（端口 3306、datadir 都在里面），启动后立刻退出
- 这个窗口 **不能关**，关窗口等于停库；看到 `ready for connections. Version: '8.0.45' ... port: 3306` 即成功
- 关库请用 `mysqladmin --user=root --password=123456 shutdown` 或 `Ctrl+C`，别直接叉窗口

**第二步：启动 Django**

```powershell
cd E:\hrms
$env:HRMS_DEBUG = "1"
E:\work_down\python\python.exe manage.py runserver 127.0.0.1:8000
```

> **务必注意**：项目默认 `DEBUG=False`（T13 安全要求），此时 `runserver` **不会**托管静态文件，`/static/...` 会返回 500，页面会变成没有样式的裸 HTML。所以演示/开发时必须显式设 `HRMS_DEBUG=1`，或改用 `manage.py runserver --insecure`。

浏览器访问 <http://127.0.0.1:8000/>。

> 生产/验收模式默认 `DEBUG=False`、`ALLOWED_HOSTS=127.0.0.1,localhost`，此时静态文件需先 `manage.py collectstatic` 由 Nginx 等托管；再叠加 `HRMS_SECURE=1` 可启用 HTTPS 重定向、HSTS、Secure Cookie。

> 关于 `mysql80` 服务：它的启动方式在这台机器上不稳定（会报 `3534` / `7009 超时` / `2186 服务没有响应控制功能`），原因是服务拉起的 mysqld 与手动实例抢同一份数据目录。日常请用上面「手动起 mysqld」的方式，不要同时开两份。

### 6. 演示账号

| 账号 | 密码 | 角色 | 可见范围 |
| --- | --- | --- | --- |
| `admin` | `admin123456` | 超级管理员 | 全部模块 |
| `deptmgr` | `deptmgr123` | 部门管理员（技术部） | 本部门员工/考勤/薪资 + 公告 |
| `staff` | `staff123` | 普通员工（张伟） | 首页、公告、我的档案/考勤/薪资、AI 智能助手（数据点评仅限本人） |

---

## 七、路由表

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 首页看板（人数、部门分布、今日考勤、待办任务） |
| `/login/` `/logout/` | GET/POST | 登录（含验证码）/ 注销 |
| `/image/code/` | GET | 图形验证码 |
| `/depart/list/` `/depart/add/` `/depart/delete/` | GET/POST | 部门列表 / 新增 / 删除 |
| `/depart/<nid>/edit/` | GET/POST | 编辑部门 |
| `/employee/list/` `/employee/add/` `/employee/delete/` | GET/POST | 员工列表（搜索+筛选+分页）/ 新增 / 删除 |
| `/employee/<nid>/edit/` `/employee/<nid>/detail/` | GET/POST | 编辑 / 详情 |
| `/attendance/list/` `/attendance/add/` `/attendance/delete/` | GET/POST | 考勤 |
| `/attendance/<nid>/edit/` | GET/POST | 编辑考勤 |
| `/salary/list/` `/salary/add/` `/salary/delete/` | GET/POST | 薪资 |
| `/salary/<nid>/edit/` | GET/POST | 编辑薪资 |
| `/announcement/list/` `/announcement/add/` `/announcement/delete/` | GET/POST | 公告 |
| `/announcement/<nid>/detail/` `/announcement/<nid>/edit/` | GET/POST | 公告详情 / 编辑 |
| `/announcement/toggle-top/` | POST | 公告置顶切换 |
| `/task/list/` `/task/add/` `/task/delete/` | GET/POST(AJAX) | 任务列表 / AJAX 新增 / 删除 |
| `/task/toggle/` | POST(AJAX) | 任务完成状态切换 |
| `/stats/` | GET | 统计页面（3 张 ECharts 图） |
| `/stats/depart-chart/` `/stats/salary-trend/` `/stats/attendance-chart/` | GET(JSON) | 图表数据接口 |
| `/system/user/list/`、`/system/user/add/`、`/system/user/delete/`、`/system/user/<nid>/edit/`、`/system/user/<nid>/reset/` | GET/POST | 用户管理（含重置密码） |
| `/system/role/list/`、`/system/role/add/`、`/system/role/delete/`、`/system/role/<nid>/edit/` | GET/POST | 角色管理 |
| `/system/permission/list/` | GET | 权限清单 |
| `/my/profile/` `/my/attendance/` `/my/salary/` | GET | 员工自助（只读） |
| `/ai/` | GET | AI 智能助手主页（四个标签页） |
| `/ai/jd/` | POST(AJAX) | 生成招聘 JD |
| `/ai/qa/` | POST(AJAX) | 制度知识库问答（返回答案 + 命中的制度） |
| `/ai/comment/` | POST(AJAX) | 考勤/薪资数据点评（返回点评 + 注入的数据文本） |
| `/ai/chat/` | POST(AJAX) | 多轮对话（前端回传 history） |
| `/ai/chat/stream/` | POST(SSE) | 流式输出（`text/event-stream`，逐词推送） |
| `/admin/` | - | Django 自带后台 |

---

## 八、关键实现说明

- **视图分层**：`views/` 包按模块拆分，`__init__.py` 统一导出，`urls.py` 只从包中导入，保持路由清晰。
- **表单样式统一**：`utils/bootstrap.py` 的 `BootstrapModelForm` 在 `__init__` 中为所有控件补 `form-control`，新增/编辑页共用 `includes/form.html` 渲染。
- **分页保留查询条件**：`utils/pagination.py` 深拷贝 `request.GET` 并重写 `page`，翻页时不丢失搜索/筛选条件。
- **验证码**：PIL 生成 4 位字符，忽略大小写校验，登录成功后立即从 session 清除。
- **AJAX 任务**：后端始终返回 JSON（成功 `{"status": true, "data": {...}}`；失败 HTTP 400 + `{"status": false, "error": {字段: [错误]}}`），前端把错误逐字段写入 `.field-error` 并保留已填内容。
- **ECharts**：三个 JSON 接口只负责取数，前端在 `stats/index.html` 中渲染饼图、柱线组合图与近 7 天考勤堆叠柱图；图表库为本地 `static/js/echarts.min.js`，离线可用。
- **日志**：`RotatingFileHandler` 分别记录普通日志、错误日志、安全日志（权限拒绝、登录失败），便于答辩演示与问题排查。

---

## 九、自测与验证

```powershell
cd E:\hrms

# 1. 静态检查
E:\work_down\python\python.exe manage.py check

# 2. 单元测试（50 个用例，含 AI 模块的 mock 用例，不联网）
E:\work_down\python\python.exe manage.py test app01

# 3. 页面冒烟（遍历 34 个地址，校验未登录跳转与越权拦截）
E:\work_down\python\python.exe scripts\smoke_check.py

# 4. T1 验收：真实调用一次大模型（需先 . .\scripts\ai_env.ps1）
E:\work_down\python\python.exe scripts\ai_selftest.py
```

最近一次验证结果（全部在 `E:\work_down\python\python.exe`、Django 5.0.14 下执行）：

- `manage.py check`：`System check identified no issues (0 silenced).`
- `manage.py test app01`：`Ran 50 tests ... OK`（约 23 秒）
- `scripts/smoke_check.py`：`检查完成：34 个地址，失败 0 个`
- `scripts/ai_selftest.py`：未配置 Key 时返回友好提示「尚未配置 AI_API_KEY…」；配置 Key 后真实调用通过（Qwen2.5-7B-Instruct 2.8 秒）
- 四个 AI 接口真实链路实测（Qwen2.5-7B-Instruct）：JD 3.9 秒、问答 2.8 秒（无命中 0 秒）、点评 1.2 秒、对话 1.8 秒、SSE 1.5 秒 / 35 个事件，结果见 `docs/self-test-record.md`

逐模块自测记录见 `docs/self-test-record.md`；AI 模块设计思路与验收步骤见 `docs/AI模块说明.md`。

---

## 十、安全配置（T13）

| 项目 | 措施 |
| --- | --- |
| CSRF | 所有 POST 表单带 `{% csrf_token %}`；AJAX 从 Cookie 取 `csrftoken` 写入请求头 |
| XSS | 模板默认转义；公告正文使用 `linebreaks` 过滤而非 `safe` |
| SQL 注入 | 全部使用 ORM，无拼接 SQL |
| 密码 | `set_password`（PBKDF2-SHA256），登录走 `authenticate()` |
| 越权 | 中间件（模块级）+ 装饰器（接口级）+ 数据范围（行级）三层 |
| 开放重定向 | `_safe_next()` 只允许站内相对路径 |
| 上传 | 头像限制类型与大小，文件名经 Django 存储重命名 |
| 响应头 | `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: same-origin` |
| Cookie | `SESSION_COOKIE_HTTPONLY=True`、`SameSite=Lax`，`HRMS_SECURE=1` 时加 `Secure` |
| 日志 | 权限拒绝与登录失败写入安全日志 |

---

## 十一、已知限制与后续可做

1. 本地演示必须 `HRMS_DEBUG=1`（`DEBUG=False` 时 `runserver` 不托管静态文件），或改用 `collectstatic` + 反向代理。
2. 项目强依赖 MySQL；换机器若没有 MySQL，需要改 `settings.py` 的 `DATABASES` 或准备等价实例。
3. 考勤暂不支持请假/加班类型，也未与薪资自动联动（扣款仍手工录入）。
4. 通知公告仅站内展示，未接入邮件/短信。
5. 若需要提交记录，可按「一个功能一次提交」的粒度初始化 Git 仓库并逐步提交。
6. AI 功能依赖外网与大模型服务：无网络 / Key 失效时只会返回友好提示，不会生成内容；答辩前先跑一次 `scripts\ai_selftest.py`。
7. 制度问答是「关键词匹配 + 提示词注入」的简化版 RAG，不是向量检索：问法过于抽象（如“公司怎么管人”）可能召回不到条目，此时按设计回答“不知道”；把对应制度补进 `ai_init.py` 并重跑命令即可。
8. 流式输出依赖浏览器 `fetch` + `ReadableStream`（Chrome/Edge 74+ 均支持），老浏览器会自动改用非流式接口。

---

## 十二、常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| 页面样式丢失、404 static | 未开启 `HRMS_DEBUG=1`，或未执行 `collectstatic` |
| 样式只恢复一半（导航栏在、侧边栏横排） | 浏览器缓存了之前失败的 `site.css`，按 `Ctrl+F5` 硬刷新 |
| `django.db.utils.OperationalError (2002/1045)` | MySQL 未启动 / 账号密码或库名不对，检查环境变量 |
| `net start mysql80` 报"服务没有报告任何错误 / 2186 不响应" | 服务拉起的 mysqld 与手动实例抢数据目录或端口。先 `mysqladmin shutdown` 掉手动实例，再用管理员窗口 `net start`；两者只能二选一 |
| 3306 被僵死 mysqld 占用、`taskkill` 报拒绝访问 | 进程在 Session 0，普通权限杀不掉；重启电脑后手动起一次 `mysqld --defaults-file=...my.ini --console` |
| `No module named 'MySQLdb'` | 未安装 PyMySQL，或 `hrms/__init__.py` 的 `install_as_MySQLdb()` 被删 |
| 登录提示验证码错误 | 验证码区分一次性，刷新页面后需重新输入 |
| `/ai/` 顶部显示“未配置 API Key” | 没设 `AI_API_KEY`，或设置后没重启 `runserver`；在启动窗口执行 `. .\scripts\ai_env.ps1` 后重启 |
| AI 调用提示“鉴权失败 / 超时 / 无法连接” | 检查 Key 是否有效、网络是否可访问 `AI_BASE_URL`、模型名是否与平台一致 |
| 制度问答回答“不知道” | 知识库没有命中相关条目：确认已执行 `manage.py ai_init`，或补充制度条目 |
| `demo_data` 报唯一约束冲突 | 先执行 `demo_data --force` 清空旧演示数据 |
