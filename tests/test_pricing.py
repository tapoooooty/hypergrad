from hip3.pricing import choose_multiplier, format_px, sanitize_ticker, sz_decimals_for, weighted_median


def test_multiplier_puts_price_in_range():
    mult, prefix = choose_multiplier(0.0000273)
    assert prefix == "M" and 1 <= 0.0000273 * mult < 1000


def test_sz_decimals_keeps_step_small():
    for px in (1.5, 27.4, 104.0, 1084.0):
        step = 10 ** -sz_decimals_for(px) * px
        assert 0.1 <= step <= 15


def test_format_px_five_significant_figures():
    assert format_px(1084.3712, 2) == "1084.4"
    assert format_px(27.41234, 1) == "27.412"
    assert format_px(123456.7, 0) == "123460"


def test_weighted_median_ignores_thin_pool():
    assert weighted_median([(1.0, 100.0), (1.01, 120.0), (5.0, 1.0)]) == 1.01


def test_ticker_is_unique():
    assert sanitize_ticker("wif", "M", {"MWIF"}) == "MWIF2"
