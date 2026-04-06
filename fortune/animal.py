"""動物占い（干支ベースのオリジナル動物占い）計算モジュール"""

# 干支に対応する動物（60干支を12動物に対応）
ETO_ANIMALS = {
    "子": {"animal": "ねずみ", "emoji": "🐭", "traits": "機敏・知恵・適応力・蓄財", "element": "水"},
    "丑": {"animal": "うし", "emoji": "🐂", "traits": "忍耐・勤勉・誠実・安定", "element": "土"},
    "寅": {"animal": "とら", "emoji": "🐯", "traits": "勇気・行動力・魅力・正義感", "element": "木"},
    "卯": {"animal": "うさぎ", "emoji": "🐰", "traits": "優雅・感受性・平和・芸術性", "element": "木"},
    "辰": {"animal": "りゅう", "emoji": "🐉", "traits": "カリスマ・野心・独自性・エネルギー", "element": "土"},
    "巳": {"animal": "へび", "emoji": "🐍", "traits": "知性・直観・神秘・変革", "element": "火"},
    "午": {"animal": "うま", "emoji": "🐴", "traits": "自由・情熱・行動力・独立心", "element": "火"},
    "未": {"animal": "ひつじ", "emoji": "🐑", "traits": "温和・創造性・共感力・芸術", "element": "土"},
    "申": {"animal": "さる", "emoji": "🐒", "traits": "機知・好奇心・社交性・多才", "element": "金"},
    "酉": {"animal": "とり", "emoji": "🐓", "traits": "完璧主義・分析力・美意識・勤勉", "element": "金"},
    "戌": {"animal": "いぬ", "emoji": "🐕", "traits": "忠実・誠実・守護・協調性", "element": "土"},
    "亥": {"animal": "いのしし", "emoji": "🐗", "traits": "純粋・情熱・大胆・誠実", "element": "水"},
}

# 天干による性格修飾
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

# 天干×地支の組み合わせによる特別な資質（一部）
SPECIAL_QUALITIES = {
    "甲子": "革新的なリーダー",
    "甲午": "独立心の強い先駆者",
    "乙丑": "忍耐強い芸術家",
    "丙寅": "情熱的な行動者",
    "丁卯": "繊細な感性を持つ平和主義者",
    "戊辰": "カリスマある実力者",
    "己巳": "知恵ある調和の人",
    "庚午": "強い意志を持つ自由人",
    "辛未": "美意識の高い調和者",
    "壬申": "機知に富んだ大局的思考の持ち主",
    "癸酉": "直感鋭い完璧主義者",
}

def get_year_animal(year: int) -> dict:
    """生まれ年の動物を取得する"""
    from .shichusuimei import EARTHLY_BRANCHES, HEAVENLY_STEMS
    branch_idx = (year - 4) % 12
    stem_idx = (year - 4) % 10
    branch = EARTHLY_BRANCHES[branch_idx]
    stem = HEAVENLY_STEMS[stem_idx]
    animal_info = ETO_ANIMALS[branch].copy()
    pillar = stem + branch
    animal_info["stem"] = stem
    animal_info["stem_modifier"] = STEM_MODIFIERS[stem]
    animal_info["pillar"] = pillar
    animal_info["special_quality"] = SPECIAL_QUALITIES.get(pillar, animal_info["traits"].split("・")[0] + "の資質")
    return animal_info

def get_compatibility(branch1: str, branch2: str) -> dict:
    """二つの地支の相性を計算する"""
    # 三合（最良の相性）
    sankai = [{"子", "辰", "申"}, {"丑", "巳", "酉"}, {"寅", "午", "戌"}, {"卯", "未", "亥"}]
    # 六合（良い相性）
    rokugo = [{"子", "丑"}, {"寅", "亥"}, {"卯", "戌"}, {"辰", "酉"}, {"巳", "申"}, {"午", "未"}]
    # 冲（対立）
    chuu = [{"子", "午"}, {"丑", "未"}, {"寅", "申"}, {"卯", "酉"}, {"辰", "戌"}, {"巳", "亥"}]

    pair = {branch1, branch2}
    for s in sankai:
        if branch1 in s and branch2 in s:
            return {"level": "最良", "description": "三合：深い縁で結ばれた最高の相性"}
    for s in rokugo:
        if pair == s:
            return {"level": "良好", "description": "六合：自然に引き合う良い相性"}
    for s in chuu:
        if pair == s:
            return {"level": "緊張", "description": "冲：刺激し合うダイナミックな関係"}
    return {"level": "普通", "description": "一般的な関係性"}

def calculate(birth_year: int, birth_month: int, birth_day: int) -> dict:
    """動物占いの計算を行う"""
    year_animal = get_year_animal(birth_year)

    # 日干支の動物も取得
    from .shichusuimei import get_day_pillar, EARTHLY_BRANCHES
    day_pillar = get_day_pillar(birth_year, birth_month, birth_day)
    day_branch = day_pillar["branch"]
    day_animal = ETO_ANIMALS[day_branch]

    # 年と日の相性
    year_branch_idx = (birth_year - 4) % 12
    from .shichusuimei import EARTHLY_BRANCHES
    year_branch = EARTHLY_BRANCHES[year_branch_idx]
    inner_outer_compatibility = get_compatibility(year_branch, day_branch)

    return {
        "year_animal": year_animal,
        "day_animal": {
            "animal": day_animal["animal"],
            "emoji": day_animal["emoji"],
            "traits": day_animal["traits"],
            "element": day_animal["element"],
            "stem": day_pillar["stem"],
            "pillar": day_pillar["pillar"],
        },
        "inner_outer_compatibility": inner_outer_compatibility,
        "personality_summary": f"表の顔は{year_animal['emoji']}{year_animal['animal']}（{year_animal['traits'].split('・')[0]}）、内なる本質は{day_animal['emoji']}{day_animal['animal']}（{day_animal['traits'].split('・')[0]}）",
    }
