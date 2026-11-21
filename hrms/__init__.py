"""项目初始化：数据库驱动适配。

优先使用 PyMySQL 顶替 MySQLdb（Windows 下免编译 mysqlclient）；
若当前解释器没有安装 PyMySQL，但装了 mysqlclient，则直接使用原生 MySQLdb。
"""

try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # 已安装 mysqlclient / MySQLdb，无需适配
    pass
