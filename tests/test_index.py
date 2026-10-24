from hip3.index import _cap_weights, level_from_prices


def test_weights_respect_cap_and_sum_to_one():
    w = _cap_weights({str(i): v for i, v in enumerate([100, 50, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1])}, 0.10)
    assert abs(sum(w.values()) - 1) < 1e-9
    assert max(w.values()) <= 0.10 + 1e-9


def test_level_is_chained():
    idx = {"units": {"a": 10.0, "b": 5.0}, "last_prices": {"a": 50.0, "b": 100.0}}
    assert level_from_prices(idx, {"a": 50.0, "b": 100.0}) == 1000.0
    assert level_from_prices(idx, {"a": 55.0}) == 1050.0
