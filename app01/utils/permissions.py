"""权限清单定义（RBAC 的单一事实来源）。

``init_data`` 命令据此生成 Permission / Role 数据，中间件、装饰器与模板
用同一套编码判断权限，避免“三处各写一遍”导致不一致。
"""

# 权限编码清单：(code, 名称, 模块, 说明)
PERMISSION_DEFS = [
    # 部门
    ("depart:view", "部门-查看", "depart", "查看部门列表"),
    ("depart:add", "部门-新增", "depart", "新建部门"),
    ("depart:edit", "部门-编辑", "depart", "修改部门"),
    ("depart:delete", "部门-删除", "depart", "删除部门"),
    # 员工
    ("employee:view", "员工-查看", "employee", "查看员工列表/详情"),
    ("employee:add", "员工-新增", "employee", "新建员工"),
    ("employee:edit", "员工-编辑", "employee", "修改员工"),
    ("employee:delete", "员工-删除", "employee", "删除员工"),
    # 考勤
    ("attendance:view", "考勤-查看", "attendance", "查看考勤记录"),
    ("attendance:add", "考勤-新增", "attendance", "录入考勤"),
    ("attendance:edit", "考勤-编辑", "attendance", "修改考勤"),
    ("attendance:delete", "考勤-删除", "attendance", "删除考勤"),
    # 薪资
    ("salary:view", "薪资-查看", "salary", "查看薪资记录"),
    ("salary:add", "薪资-新增", "salary", "录入薪资"),
    ("salary:edit", "薪资-编辑", "salary", "修改薪资"),
    ("salary:delete", "薪资-删除", "salary", "删除薪资"),
    # 公告
    ("announcement:view", "公告-查看", "announcement", "查看公告"),
    ("announcement:add", "公告-发布", "announcement", "发布公告"),
    ("announcement:edit", "公告-编辑", "announcement", "编辑公告"),
    ("announcement:delete", "公告-删除", "announcement", "删除公告"),
    # 任务
    ("task:view", "任务-查看", "task", "查看任务"),
    ("task:add", "任务-新增", "task", "新建任务（AJAX）"),
    # 统计
    ("stats:view", "统计-查看", "stats", "查看数据统计图表"),
    # AI 智能助手（招聘 JD / 制度问答 / 数据点评 / 多轮对话）
    ("ai:view", "智能助手-使用", "ai", "使用 AI 智能助手各项功能"),
    # 系统管理（用户 / 角色 / 权限）
    ("system:view", "系统-查看", "system", "查看用户与角色"),
    ("system:manage", "系统-管理", "system", "新增/编辑用户、角色与权限"),
    # 员工自助
    ("self:view", "自助-查看", "self", "查看我的档案、考勤与薪资"),
]

PERMISSION_CODES = {item[0] for item in PERMISSION_DEFS}

MODULE_NAMES = {
    "depart": "部门管理",
    "employee": "员工管理",
    "attendance": "考勤管理",
    "salary": "薪资管理",
    "announcement": "公告管理",
    "task": "任务管理",
    "stats": "数据统计",
    "system": "系统管理",
    "self": "我的",
    "ai": "智能助手",
}

# 角色定义：(code, 名称, 权限编码列表, 说明)
ROLE_DEFS = [
    (
        "superadmin",
        "超级管理员",
        sorted(PERMISSION_CODES),
        "拥有全部权限，可管理用户、角色与权限分配",
    ),
    (
        "dept_manager",
        "部门管理员",
        [
            "depart:view",
            "employee:view", "employee:add", "employee:edit", "employee:delete",
            "attendance:view", "attendance:add", "attendance:edit", "attendance:delete",
            "salary:view", "salary:add", "salary:edit", "salary:delete",
            "announcement:view", "announcement:add",
            "task:view", "task:add",
            "stats:view",
            "self:view",
            "ai:view",
        ],
        "管理本部门员工、考勤与薪资录入",
    ),
    (
        "staff",
        "普通员工",
        ["self:view", "announcement:view", "ai:view"],
        "登录后仅可查看自己的档案、考勤与薪资（只读），可使用 AI 智能助手",
    ),
]

# URL 前缀 -> 模块：中间件做“模块级”粗粒度校验，装饰器做“接口级”细粒度校验。
MODULE_URL_PREFIX = {
    "/depart/": "depart",
    "/employee/": "employee",
    "/attendance/": "attendance",
    "/salary/": "salary",
    "/announcement/": "announcement",
    "/task/": "task",
    "/stats/": "stats",
    "/system/": "system",
    "/my/": "self",
    "/ai/": "ai",
}
