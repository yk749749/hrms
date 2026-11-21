# app01/utils/retrieval.py
"""制度知识库检索（简化版 RAG 的“检索”一半）：SQL 关键词匹配 + 简单打分。

为什么不接向量数据库：课程设计要求“不引入额外依赖”，而 ``icontains`` 已经能让
回答“有据可依”；再按命中位置与命中次数排个序，效果足够演示，原理也好讲。
"""

import re

from django.db.models import Q

from app01 import models

# 只保留中文、字母、数字，标点与空白当作切分点
_SPLIT_RE = re.compile(r"[^\u4e00-\u9fa50-9a-zA-Z]+")

# 疑问词/虚词：出现频率高但没有检索价值，检索前先剥掉
_STOP_PHRASES = (
    "请问", "麻烦", "我想", "想问", "问一下", "一下", "帮我",
    "怎么样", "怎么办", "怎么", "如何", "是什么", "为什么", "有哪些", "哪个",
    "多少", "多久", "几天", "是否", "能不能", "可不可以", "可以", "需要",
    "我们", "公司", "员工", "规定", "制度",
    "吗", "呢", "吧", "啊", "的", "了", "是", "有",
)

# 2 字滑窗里常见的“无信息”组合，命中就丢掉
_STOP_GRAMS = {
    "怎么", "什么", "如何", "多少", "可以", "是否", "哪些", "哪个", "为什",
    "么样", "怎样", "请问", "一下", "我们", "公司", "员工", "制度", "规定",
    "需要", "能不", "不能", "有哪", "的话", "的是", "是什", "么情", "些情",
}


def extract_keywords(question, limit=8):
    """把一句自然语言问题切成可以拿去 SQL LIKE 的关键词。

    中文没有分词器时用一个“够用”的朴素做法：

    1. 先按标点/空白切段，并剥掉疑问词；
    2. 每个片段本身算一个关键词（适合问“报销标准”这种短问句）；
    3. 再对片段做 2 字滑窗，把“迟到怎么扣钱”切成
       迟到 / 到怎 / 怎么 / 么扣 / 扣钱，其中“怎么”被停用词表过滤掉，
       剩下的词就能命中制度原文。

    返回列表按“信息量”排序：先整段，后滑窗词，去重后最多 ``limit`` 个。
    """
    segments = [seg for seg in _SPLIT_RE.split(question or "") if seg]
    full_parts = []
    grams = []

    for seg in segments:
        for phrase in _STOP_PHRASES:
            seg = seg.replace(phrase, "")
        if len(seg) < 2:
            continue
        if seg not in full_parts:
            full_parts.append(seg)
        for i in range(len(seg) - 1):
            gram = seg[i:i + 2]
            if gram in _STOP_GRAMS or gram in grams:
                continue
            grams.append(gram)

    return (full_parts + grams)[:limit]


def search_knowledge(question, limit=3):
    """按关键词检索知识库，返回最相关的若干条（可能为空）。"""
    keywords = extract_keywords(question)
    if not keywords:
        return []

    query = Q()
    for keyword in keywords:
        query |= Q(title__icontains=keyword) | Q(content__icontains=keyword)

    # 先粗召回（最多 50 条），再在 Python 里打分排序——比一条 SQL 复杂排序更好讲
    candidates = list(models.Knowledge.objects.filter(query).order_by("id")[:50])
    if not candidates:
        return []

    def score(item):
        # 标题命中权重更高：标题就是这条制度的主题
        return sum(
            (3 if keyword in item.title else 0) + (1 if keyword in item.content else 0)
            for keyword in keywords
        )

    ranked = sorted(candidates, key=score, reverse=True)
    return [item for item in ranked if score(item) > 0][:limit]


def build_context(items, max_chars_per_item=400):
    """把命中的知识条目拼成提示词里的“资料”段落（单条过长时截断，控制 token）。"""
    blocks = []
    for item in items:
        content = (item.content or "").strip()
        if len(content) > max_chars_per_item:
            content = content[:max_chars_per_item] + "……"
        blocks.append(f"《{item.title}》\n{content}")
    return "\n\n".join(blocks)
