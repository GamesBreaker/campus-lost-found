from __future__ import annotations

import sys

import numpy as np

from app.config import settings
from app.embeddings import embed_texts
from app.errors import EmbeddingError

CASES = [
    (
        "蓝色保温杯，400ml，图书馆三楼",
        "水杯一个，深色的，三楼阅览室捡的",
        True,
    ),
    (
        "黑色长柄雨伞，教学楼",
        "雨伞，直杆那种，教室门口捡的",
        True,
    ),
    (
        "白色 AirPods 充电盒",
        "捡到一个白色耳机盒",
        True,
    ),
    (
        "蓝色保温杯",
        "黑色双肩包，食堂",
        False,
    ),
    (
        "学生证，姓李",
        "一个黑色钱包",
        False,
    ),
]


def main() -> int:
    texts = [text for case in CASES for text in case[:2]]
    print(f"provider={settings.embedding_provider} 当前阈值={settings.match_threshold:.4f}")
    try:
        vectors = embed_texts(texts)
    except EmbeddingError as exc:
        print(f"验收失败：{exc.message}", file=sys.stderr)
        return 2

    matched_scores: list[float] = []
    non_matched_scores: list[float] = []
    all_passed = True

    print("序号  期望    相似度   当前结果")
    for index, (lost_text, found_text, expected) in enumerate(CASES, start=1):
        left = vectors[(index - 1) * 2]
        right = vectors[(index - 1) * 2 + 1]
        score = float(np.dot(left, right))
        actual = score >= settings.match_threshold
        passed = actual == expected
        all_passed = all_passed and passed
        if expected:
            matched_scores.append(score)
        else:
            non_matched_scores.append(score)
        print(
            f"{index:>2}    {'匹配' if expected else '不匹配'}   {score:.4f}   "
            f"{'通过' if passed else '失败'}（{lost_text} <-> {found_text}）"
        )

    if matched_scores and non_matched_scores:
        max_non_match = max(non_matched_scores)
        min_match = min(matched_scores)
        print(f"匹配组最低分={min_match:.4f}，非匹配组最高分={max_non_match:.4f}")
        if max_non_match < min_match:
            recommended = (max_non_match + min_match) / 2
            print(
                f"五条可线性分开，分界中点为 {recommended:.4f}；"
                f"当前项目按需求使用 {settings.match_threshold:.2f}"
            )
        else:
            print("五条当前无法用单一阈值线性分开，需要检查模型或数据。")

    print("总体验收：" + ("全部通过" if all_passed else "存在失败"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
