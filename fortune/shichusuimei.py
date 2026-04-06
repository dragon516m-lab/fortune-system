"""四柱推命の基本計算モジュール"""

# 天干 (Ten Heavenly Stems)
HEAVENLY_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

# 地支 (Twelve Earthly Branches)
EARTHLY_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 五行 (Five Elements)
FIVE_ELEMENTS = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

BRANCH_ELEMENTS = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# 十二運星
TWELVE_FORTUNES = ["長生", "沐浴", "冠帯", "建禄", "帝旺", "衰", "病", "死", "墓", "絶", "胎", "養"]

# 月支（節入り基準の簡易版）
MONTH_BRANCHES = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]

# 月干の起算表 (年干 -> 月干の起点)
MONTH_STEM_START = {"甲": 0, "乙": 2, "丙": 4, "丁": 6, "戊": 8, "己": 0, "庚": 2, "辛": 4, "壬": 6, "癸": 8}

def get_year_pillar(year: int) -> dict:
    """年柱を計算する"""
    stem_idx = (year - 4) % 10
    branch_idx = (year - 4) % 12
    stem = HEAVENLY_STEMS[stem_idx]
    branch = EARTHLY_BRANCHES[branch_idx]
    return {
        "stem": stem,
        "branch": branch,
        "pillar": stem + branch,
        "element": FIVE_ELEMENTS[stem],
        "branch_element": BRANCH_ELEMENTS[branch],
    }

def get_month_pillar(year: int, month: int) -> dict:
    """月柱を計算する（簡易版）"""
    year_stem = HEAVENLY_STEMS[(year - 4) % 10]
    branch_idx = (month - 1 + 2) % 12  # 寅月スタート
    branch = EARTHLY_BRANCHES[branch_idx]
    stem_start = MONTH_STEM_START[year_stem]
    stem_idx = (stem_start + month - 1) % 10
    stem = HEAVENLY_STEMS[stem_idx]
    return {
        "stem": stem,
        "branch": branch,
        "pillar": stem + branch,
        "element": FIVE_ELEMENTS[stem],
        "branch_element": BRANCH_ELEMENTS[branch],
    }

def get_day_pillar(year: int, month: int, day: int) -> dict:
    """日柱を計算する"""
    # ユリウス日数を使った計算
    a = (14 - month) // 12
    y = year - a
    m = month + 12 * a - 2
    jd = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    stem_idx = (jd + 9) % 10
    branch_idx = (jd + 1) % 12
    stem = HEAVENLY_STEMS[stem_idx]
    branch = EARTHLY_BRANCHES[branch_idx]
    return {
        "stem": stem,
        "branch": branch,
        "pillar": stem + branch,
        "element": FIVE_ELEMENTS[stem],
        "branch_element": BRANCH_ELEMENTS[branch],
    }

def analyze_five_elements(year_pillar: dict, month_pillar: dict, day_pillar: dict) -> dict:
    """五行バランスを分析する"""
    elements = ["木", "火", "土", "金", "水"]
    count = {e: 0 for e in elements}
    for pillar in [year_pillar, month_pillar, day_pillar]:
        count[pillar["element"]] += 1
        count[pillar["branch_element"]] += 1
    strongest = max(count, key=count.get)
    weakest = min(count, key=count.get)
    return {
        "count": count,
        "strongest": strongest,
        "weakest": weakest,
    }

def calculate(birth_year: int, birth_month: int, birth_day: int) -> dict:
    """四柱推命の計算を行う"""
    year_pillar = get_year_pillar(birth_year)
    month_pillar = get_month_pillar(birth_year, birth_month)
    day_pillar = get_day_pillar(birth_year, birth_month, birth_day)
    five_elements = analyze_five_elements(year_pillar, month_pillar, day_pillar)

    return {
        "year_pillar": year_pillar,
        "month_pillar": month_pillar,
        "day_pillar": day_pillar,
        "five_elements": five_elements,
        "day_master": {
            "stem": day_pillar["stem"],
            "element": day_pillar["element"],
        },
    }
