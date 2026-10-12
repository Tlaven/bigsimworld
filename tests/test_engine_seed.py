from app.core.simulation.engine import SimulationEngine


class _Sink:
    def __init__(self):
        self.count = 0

    def put(self, item):
        self.count += 1


def _queues():
    return {"insert": _Sink(), "update": _Sink()}


def _char_dict(age=30, wealth=10000, gender="male", xing="张", name="张三"):
    return {
        "name": name, "age": age, "gender": gender, "xing": xing,
        "wealth": wealth, "DOB": None, "relationships": {},
        "status": "active", "pedometer": {"step": 0, "step_threshold": 10},
        "relation_record": {},
    }


def test_load_characters_builds_without_db():
    chars = [dict(_char_dict(), id=i) for i in range(1, 6)]
    engine = SimulationEngine(_queues(), characters=chars)
    assert len(engine.characters) == 5
    assert engine.max_id == 5


def test_load_characters_assigns_missing_ids():
    chars = [_char_dict(), _char_dict()]
    engine = SimulationEngine(_queues(), characters=chars)
    assert sorted(engine.characters.keys()) == [1, 2]
