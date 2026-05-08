"""占術を統合する計算モジュール"""

from __future__ import annotations

import datetime
from . import shichusuimei, numerology, animal, sukuyo


DEFAULT_SYSTEMS = ("shichusuimei", "numerology", "animal", "sukuyo")


def normalize_systems(selected_systems: list[str] | tuple[str, ...] | None = None) -> list[str]:
    """選択された占術を既知のキーだけに正規化する。未指定なら全占術。"""
    if not selected_systems:
        return list(DEFAULT_SYSTEMS)
    allowed = set(DEFAULT_SYSTEMS)
    normalized = [key for key in selected_systems if key in allowed]
    return normalized or list(DEFAULT_SYSTEMS)


def calculate_all(
    birth_year: int,
    birth_month: int,
    birth_day: int,
    selected_systems: list[str] | tuple[str, ...] | None = None,
) -> dict:
    """選択された占術を一括計算する"""
    systems = normalize_systems(selected_systems)
    result = {
        "birthdate": {
            "year": birth_year,
            "month": birth_month,
            "day": birth_day,
        },
        "selected_systems": systems,
    }

    if "shichusuimei" in systems:
        result["shichusuimei"] = shichusuimei.calculate(birth_year, birth_month, birth_day)
    if "numerology" in systems:
        result["numerology"] = numerology.calculate(birth_year, birth_month, birth_day)
    if "animal" in systems:
        result["animal"] = animal.calculate(birth_year, birth_month, birth_day)
    if "sukuyo" in systems:
        result["sukuyo"] = sukuyo.calculate(birth_year, birth_month, birth_day)

    return result


def calculate_sukuyo_compatibility(
    birth_year: int,
    birth_month: int,
    birth_day: int,
    partner_year: int,
    partner_month: int,
    partner_day: int,
) -> dict:
    """二人分の宿曜と相性区分を計算する。"""
    person = sukuyo.calculate(birth_year, birth_month, birth_day)
    partner = sukuyo.calculate(partner_year, partner_month, partner_day)
    compatibility = sukuyo.calculate_compatibility(person, partner)

    return {
        "person": person,
        "partner": partner,
        "compatibility": compatibility,
    }


def format_for_prompt(
    fortune_data: dict,
    concern: str,
    name: str = "",
    partner_birthdate: str = "",
    relationship: str = "",
    sukuyo_compatibility: dict | None = None,
) -> str:
    """Claude APIへのプロンプト用に占いデータをフォーマットする"""
    bd = fortune_data["birthdate"]
    systems = fortune_data.get("selected_systems") or list(DEFAULT_SYSTEMS)

    name_str = f"お名前：{name}\n" if name else ""
    today = datetime.date.today()
    today_str = f"{today.year}年{today.month}月{today.day}日"
    data_sections = []

    if "shichusuimei" in fortune_data:
        sc = fortune_data["shichusuimei"]
        data_sections.append(f"""【四柱推命データ】
・年柱：{sc['year_pillar']['pillar']}（{sc['year_pillar']['element']}×{sc['year_pillar']['branch_element']}）
・月柱：{sc['month_pillar']['pillar']}（{sc['month_pillar']['element']}×{sc['month_pillar']['branch_element']}）
・日柱（命式の中心）：{sc['day_pillar']['pillar']}（{sc['day_pillar']['element']}×{sc['day_pillar']['branch_element']}）
・日干（本質）：{sc['day_master']['stem']}（{sc['day_master']['element']}の気質）
・五行バランス：木{sc['five_elements']['count']['木']} 火{sc['five_elements']['count']['火']} 土{sc['five_elements']['count']['土']} 金{sc['five_elements']['count']['金']} 水{sc['five_elements']['count']['水']}
・最も強い気：{sc['five_elements']['strongest']} / 最も弱い気：{sc['five_elements']['weakest']}""")

    if "numerology" in fortune_data:
        num = fortune_data["numerology"]
        data_sections.append(f"""【数秘術データ】
・ライフパスナンバー：{num['life_path_number']}{'（マスターナンバー）' if num['is_master_number'] else ''}
・ライフパスの意味：{num['life_path_meaning']}
・デスティニーナンバー：{num['destiny_number']}
・デスティニーの意味：{num['destiny_meaning']}
・ソウルナンバー：{num['soul_number']}""")

    if "animal" in fortune_data:
        ani = fortune_data["animal"]
        data_sections.append(f"""【動物占いデータ】
・本命星（表の顔）：{ani['year_animal']['emoji']}{ani['year_animal']['animal']}（{ani['year_animal'].get('title', ani['year_animal']['special_quality'])} / {ani['year_animal'].get('color', '')} / {ani['year_animal'].get('number', '')}番）
・本命星の資質：{ani['year_animal']['traits']}
・干の特徴：{ani['year_animal']['stem_modifier']}
・特別な才能：{ani['year_animal']['special_quality']}
・月命星（内なる本質）：{ani['day_animal']['emoji']}{ani['day_animal']['animal']}（{ani['day_animal'].get('character', '')}）
・内面の資質：{ani['day_animal']['traits']}
・表裏の関係：{ani['inner_outer_compatibility']['description']}""")

    if "sukuyo" in fortune_data:
        sy = fortune_data["sukuyo"]
        data_sections.append(f"""【宿曜占星術データ】
・宿：{sy['shuku']}（{sy['reading']}）
・別名：{sy['alias']}
・判定補足：{sy['note']}""")

    compatibility_section = ""
    if partner_birthdate and sukuyo_compatibility:
        comp = sukuyo_compatibility["compatibility"]
        person = sukuyo_compatibility["person"]
        partner = sukuyo_compatibility["partner"]
        compatibility_section = f"""

【相性診断データ】
・人物Aの生年月日：{bd['year']}年{bd['month']}月{bd['day']}日
・人物Bの生年月日：{partner_birthdate}
・関係性：{relationship or '未指定'}
・人物Aの宿：{person['shuku']}（{person['reading']}）
・人物Bの宿：{partner['shuku']}（{partner['reading']}）
・宿曜の相性区分：{comp['category']}
・区分の意味：{comp['description']}
"""

    compatibility_summary_requirement = ""
    if partner_birthdate and sukuyo_compatibility:
        compatibility_summary_requirement = """
【二人の相性】
相性区分と関係性の核心を2〜3文で。専門用語には短い説明を添える。"""

    prompt = f"""以下の鑑定データをもとに、深みのある占い鑑定文を日本語で作成してください。

【基本情報】
{name_str}生年月日：{bd['year']}年{bd['month']}月{bd['day']}日
鑑定日（今日）：{today_str}
お悩み・ご相談：{concern}
選択された占術：{'、'.join(systems)}

{chr(10).join(data_sections)}
{compatibility_section}

【鑑定文の要件】
1. Use the astrological data above as fixed calculation results. Do not change the calculated signs, numbers, animals, or Sukuyo shuku.
2. Write the final reading in Japanese with a warm, supportive, practical tone.
3. 「お悩み・ご相談」に具体的に答えてください
4. 選択されていない占術には触れないでください
5. 出力は必ず「サマリー＋詳細」形式にしてください。サマリーを最初に書き、その後に各占術の詳細、最後に総合メッセージを書いてください。
6. サマリーだけで結論が分かるようにしてください。専門用語は使わず、300〜400文字以内、読了時間1〜2分の密度でまとめてください。

【冒頭サマリーの固定フォーマット】
━━━━━━━━━━━━━━━━
📖 鑑定結果サマリー
━━━━━━━━━━━━━━━━
【あなたの本質】
四柱推命・数秘術を中心に、核心を1〜2文で。
【今年（2026年）の流れ】
今年の運気の特徴を1〜2文で。
【恋愛・人間関係】
傾向と注意点を1〜2文で。
【仕事・キャリア】
向いている分野や働き方を1〜2文で。
【大切なメッセージ】
一番伝えたいことを1〜2文で。{compatibility_summary_requirement}
━━━━━━━━━━━━━━━━
💡 お時間のある時に、
以下で詳しく解説しています↓
━━━━━━━━━━━━━━━━

【詳細セクションの固定フォーマット】
選択されている占術だけ、以下の順番で書いてください。各占術の詳細は800〜1000文字を目安に、相談内容への具体的な答えを含めてください。

四柱推命が選択されている場合：
━━━━━━━━━━━━━━━━
🔮 四柱推命
あなたの天命と運気の流れ
━━━━━━━━━━━━━━━━
日干、命式、五行バランス、2026年の流れ、相談内容への答えを詳しく分析。

数秘術が選択されている場合：
━━━━━━━━━━━━━━━━
✨ 数秘術
人生の目的とライフパス
━━━━━━━━━━━━━━━━
ライフパス、デスティニー、ソウルナンバーから人生の目的、才能、課題を詳しく分析。

動物占いが選択されている場合：
━━━━━━━━━━━━━━━━
🐰 動物占い
表の顔と内なる本質
━━━━━━━━━━━━━━━━
表の顔、内なる本質、対人傾向、仕事や恋愛での現れ方を詳しく分析。

宿曜占星術が選択されている場合：
━━━━━━━━━━━━━━━━
🌟 宿曜占星術
人間関係と相性
━━━━━━━━━━━━━━━━
宿名、読み仮名、別名、基本性格、仕事、恋愛・人間関係、2026年の運気を詳しく分析。基本鑑定では、栄親・友衆などの宿名一覧は出さないでください。宿の相性一覧は、相性診断がオンの時だけ扱ってください。

最後に必ず以下を書いてください：
━━━━━━━━━━━━━━━━
💫 4つの占術からの総合メッセージ
━━━━━━━━━━━━━━━━
選択された占術を統合し、相談内容への答え、今後の行動指針、温かい励ましを300〜500文字で書く。
「半年後にまた運気の変わり目が来ますので、その頃にまたお声がけいただければ詳しくお伝えできます」
星龍🐉
━━━━━━━━━━━━━━━━
7. 相手の生年月日がある場合は、必ず宿曜占星術の相性診断をさらに深く追加してください：
【二人の宿】
【相性区分】
【相性分析】
【二人の未来】
この場合だけ、必要に応じて栄親・友衆・安壊・危成・業胎・命などの専門用語を使い、必ず分かりやすい説明を添えてください。注意点と活かし方を具体的に書く
8. 専門用語は必ず分かりやすく説明してください
9. 絵文字を適度に使ってください
10. 全セクションを必ず最後まで書き切ってください
11. 全体は3,800〜4,800文字を目安にしてください。選択占術が少ない場合は、その分だけ短くして構いません。
12. Markdownの # や ** は使わず、上記の見出しと区切り線をそのまま使ってください。
"""
    return prompt
