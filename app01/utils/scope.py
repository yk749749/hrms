# app01/utils/scope.py
"""数据范围控制：按“当前用户角色”收窄查询集。

规则：
- 超级管理员：全量数据；
- 部门管理员（具备 employee:view 且有 department）：只看本部门；
- 普通员工（只有 self:view）：只能看自己的数据。
"""

from app01 import models


def employee_queryset_for(user):
    """返回当前用户有权查看的员工查询集（带 select_related 优化）。"""
    queryset = models.Employee.objects.select_related("depart")
    if user.is_superuser:
        return queryset
    if user.has_perm_code("employee:view"):
        if user.department_id:
            return queryset.filter(depart_id=user.department_id)
        return queryset
    if getattr(user, "employee_id", None):
        return queryset.filter(pk=user.employee_id)
    return queryset.none()


def attendance_queryset_for(user):
    """考勤查询集（按员工范围收窄）。"""
    queryset = models.Attendance.objects.select_related("employee", "employee__depart")
    if user.is_superuser:
        return queryset
    if user.has_perm_code("attendance:view"):
        if user.department_id and not user.has_perm_code("employee:add"):
            return queryset.filter(employee__depart_id=user.department_id)
        return queryset
    if getattr(user, "employee_id", None):
        return queryset.filter(employee_id=user.employee_id)
    return queryset.none()


def salary_queryset_for(user):
    """薪资查询集（按员工范围收窄）。"""
    queryset = models.Salary.objects.select_related("employee", "employee__depart")
    if user.is_superuser:
        return queryset
    if user.has_perm_code("salary:view"):
        if user.department_id and not user.has_perm_code("employee:add"):
            return queryset.filter(employee__depart_id=user.department_id)
        return queryset
    if getattr(user, "employee_id", None):
        return queryset.filter(employee_id=user.employee_id)
    return queryset.none()
