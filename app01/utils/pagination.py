# app01/utils/pagination.py
"""可复用分页组件（T3 分页要求）。

沿用 ems 的实现思路：对 ``request.GET`` 做深拷贝后改写 ``page`` 参数，
从而在翻页时保留搜索、筛选等查询条件。
"""

import copy

from django.utils.safestring import mark_safe


class Pagination:
    """基于 queryset 切片的分页器。

    :param request: 当前请求对象，用于读取页码与其它查询参数
    :param queryset: 待分页的数据集
    :param page_size: 每页条数
    :param page_param: 页码参数名，默认 ``page``
    :param plus: 当前页前后展示的页码数量
    """

    def __init__(self, request, queryset, page_size=10, page_param="page", plus=5):
        query_dict = copy.deepcopy(request.GET)
        query_dict._mutable = True
        self.query_dict = query_dict
        self.page_param = page_param

        page = request.GET.get(page_param, "1")
        self.page = int(page) if page.isdecimal() else 1
        if self.page < 1:
            self.page = 1
        self.page_size = page_size
        self.plus = plus

        # 页码越界时回退到最后一页，避免出现空白列表
        total_count = queryset.count()
        total_page_count, div = divmod(total_count, page_size)
        if div:
            total_page_count += 1
        self.total_page_count = total_page_count
        self.total_count = total_count

        if total_page_count and self.page > total_page_count:
            self.page = total_page_count
        self.start = (self.page - 1) * page_size
        self.end = self.page * page_size
        self.page_queryset = queryset[self.start:self.end]

    def _jump_html(self):
        """生成【跳转页码】输入框 + JS。"""
        total = self.total_page_count
        param = self.page_param
        jump = (
            '<li class="pagination-jump">'
            f'<input type="number" class="form-control input-sm" min="1" max="{total}" '
            'placeholder="页码" '
            "onkeydown=\"if (event.key === 'Enter') { this.nextElementSibling.click(); }\">"
            f'<button type="button" class="btn btn-default btn-sm" data-total="{total}" '
            f'data-param="{param}" onclick="window.pageJump(this)">跳转</button>'
            "</li>"
        )
        script = (
            "<script>"
            "window.pageJump = window.pageJump || function (btn) {"
            '    var input = btn.previousElementSibling;'
            '    var total = parseInt(btn.getAttribute("data-total"), 10) || 1;'
            '    var param = btn.getAttribute("data-param") || "page";'
            "    var page = parseInt(input.value, 10);"
            "    if (isNaN(page)) { page = 1; }"
            "    if (page < 1) { page = 1; }"
            "    if (page > total) { page = total; }"
            "    var url = new URL(window.location.href);"
            "    url.searchParams.set(param, page);"
            "    window.location.href = url.toString();"
            "};"
            "</script>"
        )
        return jump + script

    def html(self, always_show=False):
        """生成分页按钮 HTML。"""
        if self.total_page_count == 0:
            return mark_safe("")
        if self.total_page_count == 1 and not always_show:
            return mark_safe("")

        if self.total_page_count <= 2 * self.plus + 1:
            start_page, end_page = 1, self.total_page_count
        elif self.page <= self.plus:
            start_page, end_page = 1, 2 * self.plus + 1
        elif self.page + self.plus > self.total_page_count:
            start_page, end_page = self.total_page_count - 2 * self.plus, self.total_page_count
        else:
            start_page, end_page = self.page - self.plus, self.page + self.plus

        parts = []
        self.query_dict.setlist(self.page_param, [1])
        parts.append(f'<li><a href="?{self.query_dict.urlencode()}">首页</a></li>')

        if self.page > 1:
            self.query_dict.setlist(self.page_param, [self.page - 1])
            parts.append(f'<li><a href="?{self.query_dict.urlencode()}">上一页</a></li>')
        else:
            parts.append('<li class="disabled"><a href="javascript:void(0);">上一页</a></li>')

        for i in range(start_page, end_page + 1):
            self.query_dict.setlist(self.page_param, [i])
            active = " active" if i == self.page else ""
            parts.append(f'<li class="page-item{active}"><a href="?{self.query_dict.urlencode()}">{i}</a></li>')

        if self.page < self.total_page_count:
            self.query_dict.setlist(self.page_param, [self.page + 1])
            parts.append(f'<li><a href="?{self.query_dict.urlencode()}">下一页</a></li>')
        else:
            parts.append('<li class="disabled"><a href="javascript:void(0);">下一页</a></li>')

        self.query_dict.setlist(self.page_param, [self.total_page_count])
        parts.append(f'<li><a href="?{self.query_dict.urlencode()}">尾页</a></li>')
        parts.append(self._jump_html())

        return mark_safe("".join(parts))
