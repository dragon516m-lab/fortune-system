"""動物占い（60分類・本命星/月命星）計算モジュール"""

from __future__ import annotations

from .shichusuimei import EARTHLY_BRANCHES, get_day_pillar, get_month_pillar


BASE_TRAITS = {
    "チータ": {"emoji": "🐆", "traits": "瞬発力・挑戦心・スピード感・勝負強さ"},
    "たぬき": {"emoji": "🦝", "traits": "愛嬌・調整力・経験知・場を和ませる力"},
    "猿": {"emoji": "🐒", "traits": "器用さ・機転・好奇心・実行力"},
    "コアラ": {"emoji": "🐨", "traits": "計画性・サービス精神・ロマン・長期視点"},
    "黒ひょう": {"emoji": "🐈‍⬛", "traits": "美意識・正義感・スマートさ・リーダー気質"},
    "虎": {"emoji": "🐯", "traits": "誠実・面倒見・バランス感覚・包容力"},
    "こじか": {"emoji": "🦌", "traits": "素直さ・愛され力・安心感・純粋さ"},
    "ゾウ": {"emoji": "🐘", "traits": "努力・集中力・職人気質・大器晩成"},
    "狼": {"emoji": "🐺", "traits": "独自性・探究心・マイペース・本質を見る力"},
    "ひつじ": {"emoji": "🐑", "traits": "協調性・共感力・人脈力・穏やかさ"},
    "ペガサス": {"emoji": "🦄", "traits": "自由・直感・天才肌・発想力"},
    "ライオン": {"emoji": "🦁", "traits": "品格・統率力・完璧主義・責任感"},
}


ANIMAL_60 = {
    1: ("チータ", "イエロー", "長距離ランナーのチータ"),
    2: ("たぬき", "グリーン", "社交家のたぬき"),
    3: ("猿", "レッド", "落ち着きのない猿"),
    4: ("コアラ", "オレンジ", "フットワークの軽いコアラ"),
    5: ("黒ひょう", "ブラウン", "面倒見のいい黒ひょう"),
    6: ("虎", "ブラック", "愛情あふれる虎"),
    7: ("チータ", "ゴールド", "全力疾走するチータ"),
    8: ("たぬき", "シルバー", "磨き上げられたたぬき"),
    9: ("猿", "ブルー", "大きな志をもった猿"),
    10: ("コアラ", "パープル", "母性豊かなコアラ"),
    11: ("こじか", "イエロー", "正直なこじか"),
    12: ("ゾウ", "グリーン", "人気者のゾウ"),
    13: ("狼", "レッド", "ネアカの狼"),
    14: ("ひつじ", "オレンジ", "協調性のないひつじ"),
    15: ("猿", "ブラウン", "どっしりした猿"),
    16: ("コアラ", "ブラック", "コアラの中のコアラ"),
    17: ("こじか", "ゴールド", "強い意志を持ったこじか"),
    18: ("ゾウ", "シルバー", "デリケートなゾウ"),
    19: ("狼", "ブルー", "放浪の狼"),
    20: ("ひつじ", "パープル", "物静かなひつじ"),
    21: ("ペガサス", "イエロー", "落ち着きのあるペガサス"),
    22: ("ペガサス", "グリーン", "強靭な翼を持つペガサス"),
    23: ("ひつじ", "レッド", "無邪気なひつじ"),
    24: ("狼", "オレンジ", "クリエイティブな狼"),
    25: ("狼", "ブラウン", "穏やかな狼"),
    26: ("ひつじ", "ブラック", "粘り強いひつじ"),
    27: ("ペガサス", "ゴールド", "波乱に満ちたペガサス"),
    28: ("ペガサス", "シルバー", "優雅なペガサス"),
    29: ("ひつじ", "ブルー", "チャレンジ精神旺盛なひつじ"),
    30: ("狼", "パープル", "順応性のある狼"),
    31: ("ゾウ", "イエロー", "リーダーとなるゾウ"),
    32: ("こじか", "グリーン", "しっかり者のこじか"),
    33: ("コアラ", "レッド", "活動的なコアラ"),
    34: ("猿", "オレンジ", "気分屋の猿"),
    35: ("ひつじ", "ブラウン", "頼られると嬉しいひつじ"),
    36: ("狼", "ブラック", "好感のもたれる狼"),
    37: ("ゾウ", "ゴールド", "まっしぐらに突き進むゾウ"),
    38: ("こじか", "シルバー", "華やかなこじか"),
    39: ("コアラ", "ブルー", "夢とロマンのコアラ"),
    40: ("猿", "パープル", "尽くす猿"),
    41: ("たぬき", "イエロー", "大器晩成のたぬき"),
    42: ("チータ", "グリーン", "足腰の強いチータ"),
    43: ("虎", "レッド", "動きまわる虎"),
    44: ("黒ひょう", "オレンジ", "情熱的な黒ひょう"),
    45: ("コアラ", "ブラウン", "サービス精神旺盛なコアラ"),
    46: ("猿", "ブラック", "守りの猿"),
    47: ("たぬき", "ゴールド", "人間味あふれるたぬき"),
    48: ("チータ", "シルバー", "品格のあるチータ"),
    49: ("虎", "ブルー", "ゆったりとした悠然の虎"),
    50: ("黒ひょう", "パープル", "落ち込みの激しい黒ひょう"),
    51: ("ライオン", "イエロー", "我が道を行くライオン"),
    52: ("ライオン", "グリーン", "統率力のあるライオン"),
    53: ("黒ひょう", "レッド", "感情豊かな黒ひょう"),
    54: ("虎", "オレンジ", "楽天的な虎"),
    55: ("虎", "ブラウン", "パワフルな虎"),
    56: ("黒ひょう", "ブラック", "気取らない黒ひょう"),
    57: ("ライオン", "ゴールド", "感情的なライオン"),
    58: ("ライオン", "シルバー", "傷つきやすいライオン"),
    59: ("黒ひょう", "ブルー", "束縛を嫌う黒ひょう"),
    60: ("虎", "パープル", "慈悲深い虎"),
}

MONTH_BRANCH_ANIMALS = {
    "子": "ひつじ",
    "丑": "黒ひょう",
    "寅": "虎",
    "卯": "たぬき",
    "辰": "狼",
    "巳": "猿",
    "午": "チータ",
    "未": "チータ",
    "申": "ペガサス",
    "酉": "こじか",
    "戌": "ゾウ",
    "亥": "ライオン",
}

STEM_MODIFIERS = {
    "甲": "積極的で開拓精神が強い",
    "乙": "柔軟で協調性がある",
    "丙": "明るく情熱的",
    "丁": "繊細で感受性豊か",
    "戊": "安定感があり信頼される",
    "己": "気配りができ調和を大切にする",
    "庚": "意志が強く決断力がある",
    "辛": "こだわりが強く美を追求する",
    "壬": "大らかで包容力がある",
    "癸": "直感が鋭く感性豊か",
}


def _pillar_number(pillar: dict) -> int:
    """甲子を1とする60干支番号を返す。"""
    stem_idx = pillar["stem_index"] if "stem_index" in pillar else None
    branch_idx = pillar["branch_index"] if "branch_index" in pillar else None
    if stem_idx is None or branch_idx is None:
        from .shichusuimei import HEAVENLY_STEMS
        stem_idx = HEAVENLY_STEMS.index(pillar["stem"])
        branch_idx = EARTHLY_BRANCHES.index(pillar["branch"])
    for n in range(60):
        if n % 10 == stem_idx and n % 12 == branch_idx:
            return n + 1
    raise ValueError("invalid pillar")


def _animal_from_number(number: int, role: str, pillar: dict | None = None) -> dict:
    animal, color, title = ANIMAL_60[number]
    base = BASE_TRAITS[animal]
    return {
        "role": role,
        "number": number,
        "animal": animal,
        "color": color,
        "title": title,
        "emoji": base["emoji"],
        "traits": base["traits"],
        "character": title,
        "element": pillar.get("branch_element", "") if pillar else "",
        "stem": pillar.get("stem", "") if pillar else "",
        "pillar": pillar.get("pillar", "") if pillar else "",
        "stem_modifier": STEM_MODIFIERS.get(pillar.get("stem", ""), "") if pillar else "",
        "special_quality": title,
    }


def _month_animal(month_pillar: dict) -> dict:
    animal = MONTH_BRANCH_ANIMALS[month_pillar["branch"]]
    base = BASE_TRAITS[animal]
    return {
        "role": "月命星（内なる本質）",
        "animal": animal,
        "emoji": base["emoji"],
        "traits": base["traits"],
        "character": f"内面に宿る{animal}の資質",
        "element": month_pillar["branch_element"],
        "stem": month_pillar["stem"],
        "pillar": month_pillar["pillar"],
        "stem_modifier": STEM_MODIFIERS.get(month_pillar["stem"], ""),
        "special_quality": f"{animal}の内的資質",
    }


def get_compatibility(animal1: str, animal2: str) -> dict:
    """二つの動物の簡易相性を計算する"""
    same_pace = [
        {"黒ひょう", "チータ", "虎", "ライオン"},
        {"ひつじ", "こじか", "たぬき"},
        {"狼", "ペガサス", "コアラ"},
        {"猿", "ゾウ"},
    ]
    if animal1 == animal2:
        return {"level": "共鳴", "description": "同じ資質を持ち、理解し合いやすい関係"}
    for group in same_pace:
        if animal1 in group and animal2 in group:
            return {"level": "良好", "description": "価値観やテンポが近く、力を合わせやすい関係"}
    return {"level": "補完", "description": "違いを活かすことで成長できる関係"}


def calculate(birth_year: int, birth_month: int, birth_day: int) -> dict:
    """動物占い60分類の計算を行う"""
    day_pillar = get_day_pillar(birth_year, birth_month, birth_day)
    month_pillar = get_month_pillar(birth_year, birth_month)
    honmei_number = _pillar_number(day_pillar)

    honmei = _animal_from_number(honmei_number, "本命星（表の顔）", day_pillar)
    getsumei = _month_animal(month_pillar)
    inner_outer_compatibility = get_compatibility(honmei["animal"], getsumei["animal"])

    return {
        "year_animal": honmei,
        "day_animal": getsumei,
        "honmei_animal": honmei,
        "getsumei_animal": getsumei,
        "inner_outer_compatibility": inner_outer_compatibility,
        "personality_summary": (
            f"本命星（表の顔）は{honmei['emoji']}{honmei['animal']}（{honmei['title']}）、"
            f"月命星（内なる本質）は{getsumei['emoji']}{getsumei['animal']}（{getsumei['traits'].split('・')[0]}）"
        ),
    }
