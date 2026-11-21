# app01/management/commands/init_data.py
"""一次性初始化：权限、角色、超级管理员账号。

用法::

    python manage.py init_data

命令可重复执行（幂等），重装环境后不必手工录入。
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from app01 import models
from app01.utils.permissions import PERMISSION_DEFS, ROLE_DEFS

User = get_user_model()


class Command(BaseCommand):
    help = "初始化权限、角色与超级管理员账号（可重复执行）"

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin", help="超级管理员用户名")
        parser.add_argument("--password", default="admin123456", help="超级管理员初始密码")

    @transaction.atomic
    def handle(self, *args, **options):
        """整段放在一个事务里：权限、角色、管理员要么全成功，要么全回滚，
        不会出现“权限建了一半、角色没绑上”的中间状态。"""
        username = options["username"]
        password = options["password"]

        # 1. 权限：用 update_or_create 按 code 幂等写入。
        #    重复执行时只更新名称/说明，不会产生重复权限项，也不会打乱已有角色绑定。
        created_perms = 0
        for code, name, module, description in PERMISSION_DEFS:
            _, created = models.Permission.objects.update_or_create(
                code=code,
                defaults={"name": name, "module": module, "description": description},
            )
            created_perms += int(created)
        self.stdout.write(f"权限同步完成：共 {len(PERMISSION_DEFS)} 项，新增 {created_perms} 项")

        # 2. 角色 + 权限绑定
        for code, name, perm_codes, description in ROLE_DEFS:
            role, _ = models.Role.objects.update_or_create(
                code=code, defaults={"name": name, "description": description}
            )
            perms = list(models.Permission.objects.filter(code__in=perm_codes))
            role.permissions.set(perms)
            self.stdout.write(f"角色 {role.name}（{role.code}）已绑定 {len(perms)} 项权限")

        # 3. 超级管理员：get_or_create 保证重复执行不报错；
        #    密码用 set_password() 走 Django 哈希，绝不直接写明文。
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"real_name": "系统管理员", "is_staff": True, "is_superuser": True},
        )
        if created or not user.is_superuser:
            user.is_superuser = True
            user.is_staff = True
            user.set_password(password)
            user.save()

        super_role = models.Role.objects.filter(code="superadmin").first()
        if super_role:
            user.roles.add(super_role)

        self.stdout.write(
            self.style.SUCCESS(
                f"超级管理员：{username} / {password}"
                + ("（已存在，仅同步角色）" if not created else "（已创建）")
            )
        )
        self.stdout.write(self.style.SUCCESS("init_data 执行完成"))
