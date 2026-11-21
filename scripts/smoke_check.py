"""页面级冒烟检查：用 Django 测试客户端遍历所有页面，快速发现模板/路由错误。

用法::

    python scripts/smoke_check.py
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hrms.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402

from app01 import models  # noqa: E402

# 冒烟脚本用测试客户端发起请求，需要放行测试主机名
if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")


def main() -> int:
    client = Client()
    admin = models.User.objects.filter(is_superuser=True).first()
    staff = models.User.objects.filter(username="staff").first()
    if not admin:
        print("缺少超级管理员，请先执行 python manage.py init_data")
        return 1

    client.force_login(admin)
    employee = models.Employee.objects.first()
    role = models.Role.objects.first()
    announcement = models.Announcement.objects.first()
    attendance = models.Attendance.objects.first()
    salary = models.Salary.objects.first()

    urls = [
        "/", "/depart/list/", "/depart/add/",
        "/employee/list/", "/employee/add/",
        "/attendance/list/", "/attendance/add/", "/salary/list/", "/salary/add/",
        "/announcement/list/", "/announcement/add/",
        "/task/list/", "/stats/", "/ai/",
        "/stats/depart-chart/", "/stats/salary-trend/", "/stats/attendance-chart/",
        "/system/user/list/", "/system/user/add/", "/system/role/list/",
        "/system/role/add/", "/system/permission/list/",
    ]
    if employee:
        urls += [f"/employee/{employee.id}/detail/", f"/employee/{employee.id}/edit/"]
    if role:
        urls += [f"/system/role/{role.id}/edit/"]
    if announcement:
        urls += [f"/announcement/{announcement.id}/detail/", f"/announcement/{announcement.id}/edit/"]
    if attendance:
        urls += [f"/attendance/{attendance.id}/edit/"]
    if salary:
        urls += [f"/salary/{salary.id}/edit/"]

    failed = 0
    for url in urls:
        try:
            response = client.get(url)
            ok = response.status_code in (200, 302)
            print(f"{'OK  ' if ok else 'FAIL'} {response.status_code:>3} {url}")
            if not ok:
                failed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR     {url} -> {exc}")
            failed += 1

    # 普通员工自助页
    if staff:
        client.force_login(staff)
        for url in ("/my/profile/", "/my/attendance/", "/my/salary/", "/employee/list/"):
            response = client.get(url)
            expect = 200 if url.startswith("/my/") else 403
            ok = response.status_code == expect
            print(f"{'OK  ' if ok else 'FAIL'} {response.status_code:>3} {url} (staff, 期望 {expect})")
            failed += int(not ok)

    # 未登录跳转
    client.logout()
    response = client.get("/employee/list/")
    print(f"{'OK  ' if response.status_code == 302 else 'FAIL'} {response.status_code:>3} /employee/list/ (未登录，期望 302)")
    failed += int(response.status_code != 302)

    print(f"\n检查完成：{len(urls) + 5} 个地址，失败 {failed} 个")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
