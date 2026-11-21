# app01/utils/code.py
"""图片验证码生成（T4）。

相比 ems 版本增加了字体兜底：找不到 Arial 时退回 PIL 内置字体，
避免换一台机器就因字体缺失报错。
"""

import random
import string

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = (
    "arial.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
)


def _load_font(size: int):
    """按候选列表加载字体，全部失败时用 PIL 默认字体。"""
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # 低版本 Pillow 不支持 size 参数
        return ImageFont.load_default()


def check_code(width=120, height=36, char_length=4, font_size=24):
    """生成图片验证码，返回 ``(Image 对象, 验证码字符串)``。"""
    code = []
    img = Image.new(mode="RGB", size=(width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img, mode="RGB")

    # 只用大写字母和数字，去掉易混淆的 O/0/I/1
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    def rnd_char():
        return random.choice(alphabet)

    def rnd_color():
        return (random.randint(0, 200), random.randint(10, 200), random.randint(60, 220))

    font = _load_font(font_size)
    char_width = width / char_length
    for i in range(char_length):
        char = rnd_char()
        code.append(char)
        draw.text(
            (i * char_width + 4, random.randint(0, 8)),
            char,
            font=font,
            fill=rnd_color(),
        )

    # 干扰点与干扰线
    for _ in range(60):
        draw.point((random.randint(0, width), random.randint(0, height)), fill=rnd_color())
    for _ in range(4):
        draw.line(
            (random.randint(0, width), random.randint(0, height),
             random.randint(0, width), random.randint(0, height)),
            fill=rnd_color(),
        )

    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    return img, "".join(code)
