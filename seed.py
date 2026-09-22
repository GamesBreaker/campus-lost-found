from __future__ import annotations

import sys

from app.config import settings
from app.db import reset_db
from app.embeddings import embed_texts
from app.errors import EmbeddingError
from app.repository import count_reports, count_users, create_report, create_user
from app.security import hash_password

DEMO_USERS = [
    ("demo_lost", "LostDemo123!"),
    ("demo_found", "FoundDemo123!"),
    ("demo_other", "OtherDemo123!"),
]

PAIRS = [
    {
        "lost": "蓝色保温杯，400ml，图书馆三楼",
        "found": "水杯一个，深色的，三楼阅览室捡的",
        "lost_location": "图书馆三楼",
        "found_location": "三楼阅览室",
        "lost_time": "今天 14:20",
        "found_time": "今天 15:10",
    },
    {
        "lost": "黑色长柄雨伞，教学楼",
        "found": "雨伞，直杆那种，教室门口捡的",
        "lost_location": "教学楼",
        "found_location": "教学楼教室门口",
        "lost_time": "周二 09:30",
        "found_time": "周二 11:00",
    },
    {
        "lost": "白色 AirPods 充电盒",
        "found": "捡到一个白色耳机盒",
        "lost_location": "操场看台",
        "found_location": "操场东侧看台",
        "lost_time": "昨晚 19:40",
        "found_time": "今天 07:50",
    },
    {
        "lost": "蓝色保温杯",
        "found": "黑色双肩包，食堂",
        "lost_location": "一食堂",
        "found_location": "二食堂",
        "lost_time": "昨天中午",
        "found_time": "今天上午",
    },
    {
        "lost": "学生证，姓李",
        "found": "一个黑色钱包",
        "lost_location": "综合楼",
        "found_location": "体育馆",
        "lost_time": "上周五",
        "found_time": "本周一",
    },
    {
        "lost": "银色折叠自行车钥匙，带蓝色挂绳",
        "found": "捡到一把小钥匙，蓝色绳子，像自行车锁钥匙",
        "lost_location": "宿舍楼下",
        "found_location": "宿舍区停车棚",
        "lost_time": "前天 18:10",
        "found_time": "前天 20:00",
    },
    {
        "lost": "黑框眼镜，右镜腿有点松",
        "found": "在自习室捡到一副眼镜，黑色边框",
        "lost_location": "第二自习室",
        "found_location": "第二自习室",
        "lost_time": "周三",
        "found_time": "周三晚",
    },
    {
        "lost": "iPhone 15，透明壳，锁屏是猫",
        "found": "捡到一部手机，透明手机壳",
        "lost_location": "校车",
        "found_location": "校车后排",
        "lost_time": "今天 08:05",
        "found_time": "今天 08:30",
    },
    {
        "lost": "红色线圈笔记本，封面有咖啡渍",
        "found": "一本红色笔记本，封面有污渍",
        "lost_location": "阶梯教室",
        "found_location": "阶梯教室",
        "lost_time": "周四 10:00",
        "found_time": "周四 12:20",
    },
    {
        "lost": "灰色围巾，羊毛的，有个小线头",
        "found": "捡到一条格子围巾，放在长椅上",
        "lost_location": "图书馆东门",
        "found_location": "中心花园长椅",
        "lost_time": "周日",
        "found_time": "周一",
    },
]


def build_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for index, pair in enumerate(PAIRS, start=1):
        suffix = f"{index:02d}"
        lost_owner = "demo_lost" if index % 2 == 1 else "demo_other"
        found_owner = "demo_found" if index % 2 == 1 else "demo_other"
        records.append(
            {
                "owner": lost_owner,
                "kind": "lost",
                "description": pair["lost"],
                "location": pair["lost_location"],
                "happened_at": pair["lost_time"],
                "contact": f"微信：demo_lost_{suffix}",
            }
        )
        records.append(
            {
                "owner": found_owner,
                "kind": "found",
                "description": pair["found"],
                "location": pair["found_location"],
                "happened_at": pair["found_time"],
                "contact": f"微信：demo_found_{suffix}",
            }
        )
    return records


def main() -> int:
    records = build_records()
    if len(records) != 20:
        print(f"演示数据必须为 20 条，当前为 {len(records)} 条。", file=sys.stderr)
        return 1

    print(f"正在用 {settings.embedding_provider} 生成 {len(records)} 条模拟数据 embedding…")
    try:
        vectors = embed_texts([record["description"] for record in records])
    except EmbeddingError as exc:
        print(f"灌库失败：{exc.message}", file=sys.stderr)
        return 2

    reset_db()
    user_ids: dict[str, int] = {}
    for username, password in DEMO_USERS:
        user = create_user(username=username, password_hash=hash_password(password))
        user_ids[username] = int(user["id"])

    for record, vector in zip(records, vectors):
        create_report(
            user_id=user_ids[record["owner"]],
            kind=record["kind"],
            description=record["description"],
            location=record["location"],
            happened_at=record["happened_at"],
            contact=record["contact"],
            embedding=vector,
        )

    print(f"完成：已写入 {count_users()} 个模拟账号和 {count_reports()} 条模拟记录。")
    print("演示账号：demo_lost / LostDemo123!，demo_found / FoundDemo123!，demo_other / OtherDemo123!")
    print("账号、帖子和联系方式均为模拟数据，不是真实校园数据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
