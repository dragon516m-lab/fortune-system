"""宿曜占星術の判定モジュール。

27宿は本来、旧暦日付と宿曜表で判定する。外部ライブラリを増やさずに
安定して動かすため、ここではユリウス日を基準にした27宿サイクルで
日々の宿を求める。
"""

from __future__ import annotations

import datetime


SHUKU_ORDER = [
    "角宿", "亢宿", "氐宿", "房宿", "心宿", "尾宿", "箕宿",
    "斗宿", "女宿", "虚宿", "危宿", "室宿", "壁宿",
    "奎宿", "婁宿", "胃宿", "昴宿", "畢宿", "觜宿", "参宿",
    "井宿", "鬼宿", "柳宿", "星宿", "張宿", "翼宿", "軫宿",
]

SHUKU_READINGS = {
    "角宿": "かくしゅく", "亢宿": "こうしゅく", "氐宿": "ていしゅく",
    "房宿": "ぼうしゅく", "心宿": "しんしゅく", "尾宿": "びしゅく",
    "箕宿": "きしゅく", "斗宿": "としゅく", "女宿": "じょしゅく",
    "虚宿": "きょしゅく", "危宿": "きしゅく", "室宿": "しつしゅく",
    "壁宿": "へきしゅく", "奎宿": "けいしゅく", "婁宿": "ろうしゅく",
    "胃宿": "いしゅく", "昴宿": "ぼうしゅく", "畢宿": "ひつしゅく",
    "觜宿": "ししゅく", "参宿": "しんしゅく", "井宿": "せいしゅく",
    "鬼宿": "きしゅく", "柳宿": "りゅうしゅく", "星宿": "せいしゅく",
    "張宿": "ちょうしゅく", "翼宿": "よくしゅく", "軫宿": "しんしゅく",
}

SHUKU_ALIASES = {
    "角宿": "始まりと開拓の星", "亢宿": "誇りと信念の星", "氐宿": "粘り強さと情の星",
    "房宿": "愛情と華やぎの星", "心宿": "感受性と洞察の星", "尾宿": "集中力と職人気質の星",
    "箕宿": "自由と行動力の星", "斗宿": "理想と人望の星", "女宿": "知性と品格の星",
    "虚宿": "感性と変化の星", "危宿": "直感と冒険の星", "室宿": "統率力と勝負運の星",
    "壁宿": "守りと信頼の星", "奎宿": "美意識と学びの星", "婁宿": "実務力と世話役の星",
    "胃宿": "情熱と突破力の星", "昴宿": "気品と審美眼の星", "畢宿": "堅実さと蓄積の星",
    "觜宿": "言葉と分析の星", "参宿": "大胆さと変革の星", "井宿": "秩序と公平の星",
    "鬼宿": "ひらめきと無垢の星", "柳宿": "情念と表現の星", "星宿": "存在感と信念の星",
    "張宿": "魅力と拡大の星", "翼宿": "理想と芸術性の星", "軫宿": "調整力と奉仕の星",
}

RELATIONSHIP_LABELS = {
    0: "命",
    1: "栄親", 2: "栄親", 26: "栄親", 25: "栄親",
    3: "友衆", 4: "友衆", 24: "友衆", 23: "友衆",
    5: "危成", 6: "危成", 22: "危成", 21: "危成",
    7: "安壊", 8: "安壊", 20: "安壊", 19: "安壊",
    9: "業胎", 18: "業胎",
}


def _julian_day(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + ((153 * m + 2) // 5) + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _shuku_index(year: int, month: int, day: int) -> int:
    # 2024-01-01を角宿に置いた27日サイクル。旧暦換算ライブラリなしでの近似基準。
    base_jd = _julian_day(2024, 1, 1)
    return (_julian_day(year, month, day) - base_jd) % 27


def _related(index: int, distances: tuple[int, ...]) -> list[str]:
    return [SHUKU_ORDER[(index + d) % 27] for d in distances]


def calculate(birth_year: int, birth_month: int, birth_day: int) -> dict:
    """生年月日から宿曜の宿と主要な相性宿を返す。"""
    date = datetime.date(birth_year, birth_month, birth_day)
    index = _shuku_index(birth_year, birth_month, birth_day)
    shuku = SHUKU_ORDER[index]
    return {
        "shuku": shuku,
        "reading": SHUKU_READINGS[shuku],
        "alias": SHUKU_ALIASES[shuku],
        "index": index,
        "birthdate": date.isoformat(),
        "eishin": _related(index, (1, 2, -1, -2)),
        "yushu": _related(index, (3, 4, -3, -4)),
        "note": "旧暦宿曜表の代替として、27宿の日次サイクルで判定しています。",
    }


def calculate_compatibility(person_a: dict, person_b: dict) -> dict:
    """二人の宿曜相性区分を返す。"""
    idx_a = int(person_a["index"])
    idx_b = int(person_b["index"])
    distance = (idx_b - idx_a) % 27
    label = RELATIONSHIP_LABELS.get(distance, "危成")
    return {
        "person_a_shuku": person_a["shuku"],
        "person_b_shuku": person_b["shuku"],
        "distance": distance,
        "category": label,
        "description": {
            "命": "同じ宿同士。似た本質を持ち、理解も反発も強く出やすい関係。",
            "栄親": "安心感と成長をもたらしやすい、育て合う相性。",
            "友衆": "刺激と共感が生まれやすい、友愛と協力の相性。",
            "安壊": "強く惹かれやすい一方、価値観の違いが課題になりやすい相性。",
            "危成": "役割や得意分野が違い、学び合いで発展しやすい相性。",
            "業胎": "過去からの縁を感じやすい、深いテーマを持つ相性。",
        }[label],
    }
