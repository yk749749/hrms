"""
Django settings for hrms project.

企业员工管理系统（HRMS）全局配置：
- Django 5.2 + MySQL
- 中文（zh-hans）、东八区
- 自定义用户模型 app01.User（继承 AbstractUser）
- 分级日志 / 安全响应头（T13）
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 基础配置：敏感项一律从环境变量读取，代码里不硬编码
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "HRMS_SECRET_KEY",
    "django-insecure-hrms-dev-only-2v#9k!q7x$w&4mz^0p@8r3t5n6b1c",
)

# T13：默认关闭 DEBUG，本地开发可通过环境变量 HRMS_DEBUG=1 打开
DEBUG = os.environ.get("HRMS_DEBUG", "0") == "1"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("HRMS_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "app01.apps.App01Config",
]

MIDDLEWARE = [
    # Django 内置中间件：顺序不能乱。
    # - SessionMiddleware 必须在 AuthenticationMiddleware 之前，因为后者要靠 session 取用户；
    # - CsrfViewMiddleware 必须在业务视图之前，保证所有 POST 都经过 CSRF 校验。
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # 业务中间件：登录拦截（T4）+ 模块级权限校验（T5）。
    # AuthMiddleware 必须排在 PermissionMiddleware 前面：先确认“有没有登录”，
    # 再判断“有没有这个模块的权限”，否则未登录用户会直接看到 403 而不是登录页。
    "app01.middleware.auth.AuthMiddleware",
    "app01.middleware.rbac.PermissionMiddleware",
]

ROOT_URLCONF = "hrms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # 前端按权限隐藏按钮：模板里可直接使用 perms_codes
                "app01.utils.context_processors.permission_codes",
            ],
        },
    },
]

WSGI_APPLICATION = "hrms.wsgi.application"

# ---------------------------------------------------------------------------
# 数据库：MySQL
# 说明：默认值直接写成本机参数，保证 clone 下来能直接跑；换环境时用环境变量覆盖。
# 表统一使用 utf8mb4，才能正确保存生僻姓名与 emoji；Django 侧通过
# OPTIONS 里的字符集参数保证连接也是 utf8mb4（否则可能出现中文乱码）。
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('HRMS_DB_NAME', 'hrms'),
        'USER': os.environ.get('HRMS_DB_USER', 'root'),
        'PASSWORD': os.environ.get('HRMS_DB_PASSWORD', '123456'),
        'HOST': os.environ.get('HRMS_DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('HRMS_DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# 自定义用户模型（T1 / T4）
AUTH_USER_MODEL = "app01.User"

# 密码哈希：Django 默认 PBKDF2-SHA256（严禁明文 / 裸 MD5）。
# 列表里依次是“首选算法 + 兼容算法”：校验旧密码时 Django 会按顺序尝试，
# 因此将来换算法（如 Argon2）也不会导致老用户登录失败。
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# 国际化
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# 静态文件与媒体文件（员工头像上传）
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 登录相关跳转
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# 图片上传大小上限（2MB）：与表单里的头像校验保持一致。
# 这一项同时限制“整个请求体”的大小，防止有人绕过前端直接 POST 超大文件。
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# ---------------------------------------------------------------------------
# T13 安全加固：安全响应头与 Cookie 策略
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # 前端 AJAX 需要读取 csrftoken，再放进 X-CSRFToken 请求头
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# 生产环境（HTTPS）打开以下三项：设置 HRMS_SECURE=1
if os.environ.get("HRMS_SECURE", "0") == "1":
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# 分级日志：INFO 落文件、WARNING 以上同时输出控制台，权限拒绝单独留痕
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}:{lineno} {message}",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "WARNING",
        },
        "file_all": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "hrms.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
            "encoding": "utf-8",
        },
        "file_error": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "error.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "ERROR",
            "encoding": "utf-8",
        },
        "file_security": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "security.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "WARNING",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["file_error", "console"],
            "level": "ERROR",
            "propagate": False,
        },
        "hrms": {
            "handlers": ["console", "file_all"],
            "level": "INFO",
            "propagate": False,
        },
        # 权限拒绝 / 登录失败等安全事件
        "hrms.security": {
            "handlers": ["file_security", "console"],
            "level": "WARNING",
            "propagate": False,
        },
        # 大模型调用（记录耗时、模型名、失败原因；不记录 Key 与完整提示词）
        "hrms.ai": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# 大模型（AI 智能助手）配置
# 说明：Key / 地址 / 模型名一律从环境变量读取，代码里不硬编码、不进 Git。
#       方式 A（当前窗口有效）：. .\scripts\ai_env.ps1，然后启动 runserver；
#       方式 B（永久生效）：写入系统环境变量，重开终端。
# ---------------------------------------------------------------------------
AI_API_KEY = os.environ.get("AI_API_KEY", "")

# 硅基流动（SiliconFlow，OpenAI 兼容接口）：换服务商只需改这一行
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")

# 模型名从平台「模型广场」复制完整名称（含“组织/”前缀）
AI_MODEL = os.environ.get("AI_MODEL", "Qwen/Qwen2.5-7B-Instruct")

# 调用参数：超时（秒）、随机度、单次最大生成 token
AI_TIMEOUT = float(os.environ.get("AI_TIMEOUT", "30"))
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.7"))
AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "800"))

# 输入过滤（T6）：单条用户输入最大字符数
AI_MAX_INPUT = int(os.environ.get("AI_MAX_INPUT", "400"))

# 多轮对话（T5）：保留最近多少“轮”（一问一答算 2 条消息）
AI_HISTORY_TURNS = int(os.environ.get("AI_HISTORY_TURNS", "4"))
