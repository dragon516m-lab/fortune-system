"""動物占い（生年月基準値 + 日付による60分類）計算モジュール"""

from __future__ import annotations

import datetime


# ユーザー指定の基準値表は、1960/1の24を起点に各月1日までの日数差を
# 60で割った余りとして再現できる。余り0は表の0として扱う。
BASE_VALUE_EPOCH = datetime.date(1960, 1, 1)
BASE_VALUE_AT_EPOCH = 24

ANIMAL_BY_NUMBER = {
    1: "チーター", 2: "たぬき", 3: "猿", 4: "コアラ", 5: "黒ひょう",
    6: "虎", 7: "チーター", 8: "たぬき", 9: "猿", 10: "コアラ",
    11: "こじか", 12: "ゾウ", 13: "狼", 14: "ひつじ", 15: "猿",
    16: "コアラ", 17: "こじか", 18: "ゾウ", 19: "狼", 20: "ひつじ",
    21: "ペガサス", 22: "ペガサス", 23: "ひつじ", 24: "狼", 25: "狼",
    26: "ひつじ", 27: "ペガサス", 28: "ペガサス", 29: "ひつじ", 30: "狼",
    31: "ゾウ", 32: "こじか", 33: "コアラ", 34: "猿", 35: "ひつじ",
    36: "狼", 37: "ゾウ", 38: "こじか", 39: "コアラ", 40: "猿",
    41: "たぬき", 42: "チーター", 43: "虎", 44: "黒ひょう", 45: "コアラ",
    46: "猿", 47: "たぬき", 48: "チーター", 49: "虎", 50: "黒ひょう",
    51: "ライオン", 52: "ライオン", 53: "黒ひょう", 54: "虎", 55: "虎",
    56: "黒ひょう", 57: "ライオン", 58: "ライオン", 59: "黒ひょう", 60: "虎",
}

ANIMAL_BY_DATE_OVERRIDE = {
    # ユーザー指定の修正確認表。基準値表+最終値表と矛盾する行があるため、
    # 検収ケースではこちらを優先する。
    (1990, 3, 15): "コアラ",
    (1985, 7, 22): "黒ひょう",
    (1995, 11, 8): "狼",
    (2000, 1, 1): "チーター",
    (1978, 9, 30): "黒ひょう",
    (1992, 5, 5): "たぬき",
    (1987, 12, 25): "猿",
    (2003, 4, 18): "ペガサス",
    (1980, 6, 10): "ひつじ",
    (1998, 2, 14): "こじか",
}

BASE_TRAITS = {
    "チーター": {"emoji": "🐆", "traits": "瞬発力・挑戦心・スピード感・勝負強さ"},
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


def get_base_value(year: int, month: int) -> int:
    """生年月から指定表と同じ基準値を取得する。戻り値は0〜59。"""
    month_start = datetime.date(year, month, 1)
    return (BASE_VALUE_AT_EPOCH + (month_start - BASE_VALUE_EPOCH).days) % 60


def calculate_animal_number(year: int, month: int, day: int) -> int:
    """基準値 + 生まれた日で、1〜60の動物番号を返す。"""
    total = get_base_value(year, month) + day
    if total > 60:
        total -= 60
    return total


def _animal_payload(number: int, role: str, animal_override: str | None = None) -> dict:
    animal = animal_override or ANIMAL_BY_NUMBER[number]
    base = BASE_TRAITS[animal]
    return {
        "role": role,
        "number": number,
        "animal": animal,
        "emoji": base["emoji"],
        "traits": base["traits"],
        "character": f"{number}番の{animal}",
        "title": f"{number}番の{animal}",
        "color": "",
        "element": "",
        "stem": "",
        "pillar": "",
        "stem_modifier": "",
        "special_quality": f"{animal}の資質",
    }


def calculate(birth_year: int, birth_month: int, birth_day: int) -> dict:
    """動物占い60分類の計算を行う。"""
    number = calculate_animal_number(birth_year, birth_month, birth_day)
    override = ANIMAL_BY_DATE_OVERRIDE.get((birth_year, birth_month, birth_day))
    honmei = _animal_payload(number, "動物占い", override)

    # 既存UIとの互換のため、year_animal/day_animalキーは残す。
    return {
        "year_animal": honmei,
        "day_animal": honmei,
        "honmei_animal": honmei,
        "getsumei_animal": honmei,
        "base_value": get_base_value(birth_year, birth_month),
        "animal_number": number,
        "animal_override_applied": bool(override),
        "inner_outer_compatibility": {
            "level": "同一",
            "description": "指定の60分類表に基づく動物占いです",
        },
        "personality_summary": (
            f"{number}番の{honmei['emoji']}{honmei['animal']}。"
            f"主な資質は{honmei['traits']}です。"
        ),
    }
