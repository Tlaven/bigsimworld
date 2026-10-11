from app.core.measure.measure import Measure, measure_from_characters
from app.core.measure.space import StateSpace
from app.core.measure.survey import measure_survey
from bench.world import build_engine


def test_measure_survey_totals():
    space = StateSpace()
    engine = build_engine(2000, seed=1)
    m = measure_from_characters(engine.characters.values(), space)
    survey = measure_survey(m, space)
    assert sum(survey["age"][1]) == len(engine.characters)
    assert sum(survey["wealth"][1]) == len(engine.characters)
    assert len(survey["age"][0]) == len(survey["age"][1])
    assert len(survey["wealth"][0]) == len(survey["wealth"][1])


def test_measure_survey_hand_built():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(3, 0, space.wealth_bucket(5000), 0), 10)   # age 3 -> "0-4"
    m.add(space.encode(72, 1, space.wealth_bucket(5000), 0), 5)   # age 72 -> "70-74"
    survey = measure_survey(m, space)
    labels = survey["age"][0]
    counts = survey["age"][1]
    assert counts[labels.index("0-4")] == 10
    assert counts[labels.index("70-74")] == 5
    assert sum(counts) == 15
