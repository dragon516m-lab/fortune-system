"""三つの占術を統合する計算モジュール"""

import datetime
from . import shichusuimei, numerology, animal


def calculate_all(birth_year: int, birth_month: int, birth_day: int) -> dict:
    """四柱推命・数秘術・動物占いを一括計算する"""
    shichusuimei_result = shichusuimei.calculate(birth_year, birth_month, birth_day)
    numerology_result = numerology.calculate(birth_year, birth_month, birth_day)
    animal_result = animal.calculate(birth_year, birth_month, birth_day)

    return {
        "birthdate": {
            "year": birth_year,
            "month": birth_month,
            "day": birth_day,
        },
        "shichusuimei": shichusuimei_result,
        "numerology": numerology_result,
        "animal": animal_result,
    }


def format_for_prompt(fortune_data: dict, concern: str, name: str = "") -> str:
    """Claude APIへのプロンプト用に占いデータをフォーマットする"""
    sc = fortune_data["shichusuimei"]
    num = fortune_data["numerology"]
    ani = fortune_data["animal"]
    bd = fortune_data["birthdate"]

    name_str = f"お名前：{name}\n" if name else ""
    today = datetime.date.today()
    today_str = f"{today.year}年{today.month}月{today.day}日"

    prompt = f"""以下の鑑定データをもとに、深みのある占い鑑定文を日本語で作成してください。

【基本情報】
{name_str}生年月日：{bd['year']}年{bd['month']}月{bd['day']}日
鑑定日（今日）：{today_str}
お悩み・ご相談：{concern}

【四柱推命データ】
・年柱：{sc['year_pillar']['pillar']}（{sc['year_pillar']['element']}×{sc['year_pillar']['branch_element']}）
・月柱：{sc['month_pillar']['pillar']}（{sc['month_pillar']['element']}×{sc['month_pillar']['branch_element']}）
・日柱（命式の中心）：{sc['day_pillar']['pillar']}（{sc['day_pillar']['element']}×{sc['day_pillar']['branch_element']}）
・日干（本質）：{sc['day_master']['stem']}（{sc['day_master']['element']}の気質）
・五行バランス：木{sc['five_elements']['count']['木']} 火{sc['five_elements']['count']['火']} 土{sc['five_elements']['count']['土']} 金{sc['five_elements']['count']['金']} 水{sc['five_elements']['count']['水']}
・最も強い気：{sc['five_elements']['strongest']} / 最も弱い気：{sc['five_elements']['weakest']}

【数秘術データ】
・ライフパスナンバー：{num['life_path_number']}{'（マスターナンバー）' if num['is_master_number'] else ''}
・ライフパスの意味：{num['life_path_meaning']}
・デスティニーナンバー：{num['destiny_number']}
・デスティニーの意味：{num['destiny_meaning']}
・ソウルナンバー：{num['soul_number']}

【動物占いデータ】
・表の顔（年干支）：{ani['year_animal']['emoji']}{ani['year_animal']['animal']}（{ani['year_animal']['pillar']}）
・資質：{ani['year_animal']['traits']}
・干の特徴：{ani['year_animal']['stem_modifier']}
・特別な才能：{ani['year_animal']['special_quality']}
・内なる本質（日干支）：{ani['day_animal']['emoji']}{ani['day_animal']['animal']}
・内面の資質：{ani['day_animal']['traits']}
・表裏の関係：{ani['inner_outer_compatibility']['description']}

【鑑定文の要件】
1. 上記のデータを統合した鑑定文を日本語で作成してください
2. 「お悩み・ご相談」に具体的に答えてください
3. 温かみがあり、励ましと希望を与える文体にしてください
4. 必ず以下の5つのセクションをすべて書いてください（各100〜150字）：
   【あなたの本質と天命】
   【{concern[:10]}についての鑑定】
   【強みとチャンスの時期】
   【開運アドバイス】
   【総合メッセージ】
5. 絵文字を適度に使ってください
6. 全セクションを必ず最後まで書き切ってください
"""
    return prompt
