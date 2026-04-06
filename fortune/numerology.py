"""数秘術の計算モジュール"""

MASTER_NUMBERS = {11, 22, 33}

LIFE_PATH_MEANINGS = {
    1: "リーダーシップ・独立心・開拓者精神。自分の道を切り開く力を持つ。",
    2: "協調性・感受性・調和。人と人をつなぐ架け橋の役割。",
    3: "創造性・表現力・社交性。喜びと楽しさを周囲に与える才能。",
    4: "安定・実直・勤勉。地に足のついた着実な努力家。",
    5: "自由・変化・冒険心。多様な経験を通じて成長する。",
    6: "責任感・愛情・奉仕。家族や仲間を大切にする調和の人。",
    7: "知性・分析力・精神性。真理を追い求める探求者。",
    8: "力・繁栄・野心。物質的成功と精神的豊かさのバランス。",
    9: "人道主義・完成・慈悲。大きな愛で世界に貢献する。",
    11: "直観・インスピレーション・精神的覚醒。高い霊感を持つマスターナンバー。",
    22: "マスタービルダー・大きなビジョン・実現力。夢を現実に変える力。",
    33: "マスターティーチャー・愛と奉仕・高い精神性。人類への奉仕と教えを使命とする。",
}

DESTINY_NUMBER_MEANINGS = {
    1: "指導者・先駆者としての運命",
    2: "仲介者・協力者としての運命",
    3: "表現者・エンターテイナーとしての運命",
    4: "建設者・組織者としての運命",
    5: "冒険者・変革者としての運命",
    6: "養育者・奉仕者としての運命",
    7: "探求者・分析者としての運命",
    8: "達成者・経営者としての運命",
    9: "人道主義者・完成者としての運命",
    11: "インスピレーター・ビジョナリーとしての運命",
    22: "マスタービルダーとしての壮大な運命",
    33: "マスターティーチャーとしての神聖な運命",
}

def reduce_number(n: int) -> int:
    """数字をマスターナンバーを保ちながら一桁に還元する"""
    while n > 9 and n not in MASTER_NUMBERS:
        n = sum(int(d) for d in str(n))
    return n

def calculate_life_path(year: int, month: int, day: int) -> int:
    """ライフパスナンバーを計算する"""
    month_reduced = reduce_number(month)
    day_reduced = reduce_number(day)
    year_reduced = reduce_number(sum(int(d) for d in str(year)))
    total = month_reduced + day_reduced + year_reduced
    return reduce_number(total)

def calculate_destiny_number(year: int, month: int, day: int) -> int:
    """デスティニーナンバー（誕生日全体）を計算する"""
    all_digits = str(year) + str(month).zfill(2) + str(day).zfill(2)
    total = sum(int(d) for d in all_digits)
    return reduce_number(total)

def calculate_soul_number(year: int, month: int, day: int) -> int:
    """ソウルナンバー（魂の番号）を計算する - 月日のみ"""
    total = month + day
    return reduce_number(total)

def calculate(birth_year: int, birth_month: int, birth_day: int) -> dict:
    """数秘術の計算を行う"""
    life_path = calculate_life_path(birth_year, birth_month, birth_day)
    destiny = calculate_destiny_number(birth_year, birth_month, birth_day)
    soul = calculate_soul_number(birth_year, birth_month, birth_day)

    return {
        "life_path_number": life_path,
        "life_path_meaning": LIFE_PATH_MEANINGS.get(life_path, ""),
        "destiny_number": destiny,
        "destiny_meaning": DESTINY_NUMBER_MEANINGS.get(destiny, ""),
        "soul_number": soul,
        "is_master_number": life_path in MASTER_NUMBERS,
    }
