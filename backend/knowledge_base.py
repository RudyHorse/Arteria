"""Knowledge base of laboratory parameters.

Aliases are normalized (lowercase, latin homoglyphs mapped) before matching.
Used to canonicalize test names and supply default units.
"""

_PARAMETERS = [
    # (canonical name, [aliases...], default unit)
    ("Лейкоциты (WBC)", ["лейкоциты", "wbc", "leikocity"], "*10^9/л"),
    ("Эритроциты (RBC)", ["эритроциты", "rbc", "eritrocity"], "*10^12/л"),
    ("Гемоглобин (HGB)", ["гемоглобин", "hgb", "gemoglobin"], "г/л"),
    ("Гематокрит (HCT)", ["гематокрит", "hct", "gematokrit"], "%"),
    ("Средний объем эритроцита (MCV)", ["средний объем эритроцита", "mcv"], "fL"),
    ("Средн. сод. гемоглобина (MCH)", ["средн. сод. гемоглобина", "mch"], "пг"),
    ("Средн. конц. гемоглобина (MCHC)", ["средн. конц. гемоглобина", "mchc"], "г/л"),
    ("RDW-SD", ["rdw-sd", "распр. эрит. по v - станд отклон", "станд отклон"], "fL"),
    ("RDW-CV", ["rdw-cv", "распр. эрит. по v - коэф. вариац", "коэф. вариац"], "%"),
    ("Тромбоциты (PLT)", ["тромбоциты", "plt", "trombocity"], "*10^9/л"),
    ("PDW", ["pdw", "распр. тромбоцитов по объему"], "fL"),
    ("Средний объем тромбоцита (MPV)", ["средний объем тромбоцита", "mpv"], "fL"),
    ("Коэффициент больших тромбоцитов (P-LCR)", ["коэффициент больших тромбоцитов", "p-lcr", "plcr"], "%"),
    ("Нейтрофилы (NE)", ["нейтрофилы", "ne", "nejtrofily"], "*10^9/л"),
    ("Лимфоциты (LY)", ["лимфоциты", "ly", "limfocity"], "*10^9/л"),
    ("Моноциты (MO)", ["моноциты", "mo", "monocity"], "*10^9/л"),
    ("Эозинофилы (EO)", ["эозинофилы", "eo", "eozinofily"], "*10^9/л"),
    ("Базофилы (BA)", ["базофилы", "ba", "bazofily"], "*10^9/л"),
    ("Нейтрофилы, % (NE%)", ["нейтрофилы, %", "ne%"], "%"),
    ("Лимфоциты, % (LY%)", ["лимфоциты, %", "ly%"], "%"),
    ("Моноциты, % (MO%)", ["моноциты, %", "mo%"], "%"),
    ("Эозинофилы, % (EO%)", ["эозинофилы, %", "eo%"], "%"),
    ("Базофилы, % (BA%)", ["базофилы, %", "ba%"], "%"),
    ("Гликированный гемоглобин (HbA1c)", ["гликированный гемоглобин", "hba1c"], "%"),
    ("Среднесуточный уровень глюкозы плазмы (ССГП)", ["среднесуточный уровень глюкозы", "ссгп"], "ммоль/л"),
    ("СОЭ", ["скорость оседания эритроцитов", "скорость оседания", "соэ"], "мм/ч"),
    ("Холестерол общий", ["холестерол общий", "холестерол", "холестерин", "общий холестерин"], "ммоль/л"),
    ("ЛПНП", ["лпнп", "липопротеины низкой плотности", "холестерол - липопротеины"], "ммоль/л"),
    ("Триглицериды", ["триглицериды"], "ммоль/л"),
    ("АЛТ", ["аланинаминотрансфераза", "алт", "alat"], "Ед/л"),
    ("АСТ", ["аспартатаминотрансфераза", "аст", "asat"], "Ед/л"),
    ("ГГТ", ["гамма-глютамилтранспептидаза", "гамма-гт", "ггт", "ggt"], "Ед/л"),
    ("Креатинин", ["креатинин в сыворотке", "креатинин"], "мкмоль/л"),
    ("СКФ (CKD-EPI)", ["скорость клубочковой фильтрации", "скф", "ckd-epi"], "мл/мин/1,73м^2"),
    ("Билирубин общий", ["билирубин общий", "билирубин"], "мкмоль/л"),
    ("ПСА общий", ["простатспецифический антиген", "пса общий", "пса"], "нг/мл"),
    ("Глюкоза", ["глюкоза в плазме", "глюкоза"], "ммоль/л"),
    ("HBsAg", ["hbsag"], None),
    ("HCV, антитела", ["hcv"], None),
    ("ВИЧ-1/ВИЧ-2, антитела, антиген p24", ["вич-1", "вич-2", "антиген p24", "вич"], None),
    ("Treponema pallidum, антитела", ["treponema", "сифилис"], None),
    ("Железо", ["железо сывороточное", "железо"], "мкмоль/л"),
    ("Ферритин", ["ферритин"], "нг/мл"),
    ("Витамин B12", ["витамин b12", "витамин в12"], "пг/мл"),
    ("С-реактивный белок (СРБ)", ["с-реактивный белок", "срб", "c-реактивный белок", "crp"], "мг/л"),
    ("Мочевина", ["мочевина"], "ммоль/л"),
    ("Общий белок", ["общий белок", "белок общий"], "г/л"),
    ("Калий", ["калий"], "ммоль/л"),
    ("Натрий", ["натрий"], "ммоль/л"),
    ("Щелочная фосфатаза (ЩФ)", ["щелочная фосфатаза", "щф", "alp"], "Ед/л"),
]

_GENERIC_RAW_NAMES = [
    "концентрация", "активность", "доля", "доля, %",
    "скорость оседания", "результат",
]

_TEXT_RESULTS = {
    "ОТРИЦАТЕЛЬНЫЙ", "отрицательный", "ПОЛОЖИТЕЛЬНЫЙ", "положительный",
    "не обнаружено", "не обнаружен", "обнаружено", "следы",
    "слабоположительный", "negative", "positive", "not detected",
}


def _norm(s: str) -> str:
    from ocr_processor import _norm_key
    return _norm_key(s)


def _norm_generic(s: str) -> str:
    return _norm(s).replace(",", "").replace(".", "").strip()


_GENERIC_NORM = {_norm_generic(g) for g in _GENERIC_RAW_NAMES}

_PARAM_BY_ALIAS = {}


def _build_index():
    if _PARAM_BY_ALIAS:
        return
    for canonical, aliases, unit in _PARAMETERS:
        for a in aliases:
            _PARAM_BY_ALIAS[_norm(a)] = (canonical, unit)
        _PARAM_BY_ALIAS[_norm(canonical)] = (canonical, unit)


def resolve_parameter(name: str):
    """Return (canonical_name, default_unit) for a known parameter.

    Exact normalized alias match first, then longest substring alias match
    (for section titles like "Холестерол - Липопротеины низкой плотности (ЛПНП)").
    """
    _build_index()
    n = _norm(name).strip()
    exact = _PARAM_BY_ALIAS.get(n)
    if exact:
        return exact
    best = None
    for alias, (canonical, unit) in _PARAM_BY_ALIAS.items():
        if len(alias) >= 5 and alias in n:
            if best is None or len(alias) > len(best[0]):
                best = (alias, canonical, unit)
    if best:
        return best[1], best[2]
    return None, None


def is_generic_row_name(name: str) -> bool:
    return _norm_generic(name) in _GENERIC_NORM


def is_text_result(s: str) -> bool:
    return (s or "").strip() in _TEXT_RESULTS
