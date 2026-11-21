/* 站点公共脚本：AJAX CSRF、删除确认、图表自适应 */
(function () {
    "use strict";

    // 从 cookie 读取 csrftoken，供 $.ajax 使用
    window.getCsrfToken = function () {
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : "";
    };

    // 统一为 jQuery 的 AJAX 请求带上 CSRF 头
    if (window.jQuery && jQuery.ajaxSetup) {
        jQuery.ajaxSetup({
            beforeSend: function (xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/.test(settings.type)) {
                    xhr.setRequestHeader("X-CSRFToken", window.getCsrfToken());
                }
            }
        });
    }

    // 删除按钮确认（data-confirm）
    document.addEventListener("click", function (event) {
        var el = event.target.closest("[data-confirm]");
        if (!el) { return; }
        if (!window.confirm(el.getAttribute("data-confirm"))) {
            event.preventDefault();
        }
    });
})();
