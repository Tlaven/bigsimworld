def test_roundtrip():
    from app.core.measure.space import StateSpace

    s = StateSpace()
    for state in [(0, 0, 0, 0), (120, 1, 47, 2), (60, 1, 10, 1)]:
        assert s.decode(s.encode(*state)) == state


def test_size():
    from app.core.measure.space import StateSpace

    s = StateSpace(age_buckets=121, genders=2, wealth_bins=48, maritals=3)
    assert s.size == 121 * 2 * 48 * 3


def test_encode_bijective_on_grid():
    from app.core.measure.space import StateSpace

    s = StateSpace(age_buckets=5, genders=2, wealth_bins=4, maritals=3)
    seen = {s.encode(a, g, w, m)
            for a in range(5) for g in range(2) for w in range(4) for m in range(3)}
    assert len(seen) == s.size


def test_wealth_bucket_monotone():
    from app.core.measure.space import StateSpace

    s = StateSpace()
    assert s.wealth_bucket(1) <= s.wealth_bucket(1000) <= s.wealth_bucket(1_000_000)


def test_wealth_value_roundtrip_within_bucket():
    from app.core.measure.space import StateSpace

    s = StateSpace()
    for value in (5000.0, 50000.0, 500000.0):
        ratio = s.wealth_value(s.wealth_bucket(value)) / value
        assert 0.5 <= ratio <= 2.0
