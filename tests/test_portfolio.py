"""Tests for portfolio state."""

from __future__ import annotations

from datetime import date

import pytest

from ktok.state.portfolio import STARTING_CASH, Portfolio


def test_fresh_portfolio_has_starting_cash():
    p = Portfolio.fresh()
    assert p.cash_chf == STARTING_CASH
    assert p.day == date.today()
    assert all(h.ktokens == 0 for h in p.holdings.values())


def test_buy_reduces_cash_and_adds_tokens():
    p = Portfolio.fresh()
    p.buy("opus", kt=100, price_chf_per_kt=0.4)
    assert p.cash_chf == pytest.approx(STARTING_CASH - 40.0)
    assert p.holding("opus").ktokens == 100
    assert p.holding("opus").avg_cost_chf_per_kt == pytest.approx(0.4)


def test_buy_updates_average_cost():
    p = Portfolio.fresh()
    p.buy("opus", kt=100, price_chf_per_kt=0.4)
    p.buy("opus", kt=100, price_chf_per_kt=0.6)
    # avg of 100 @ 0.4 and 100 @ 0.6 = 0.5
    assert p.holding("opus").avg_cost_chf_per_kt == pytest.approx(0.5)
    assert p.holding("opus").ktokens == 200


def test_buy_fails_without_cash():
    p = Portfolio.fresh()
    with pytest.raises(ValueError):
        p.buy("opus", kt=1_000_000, price_chf_per_kt=1.0)


def test_sell_reduces_tokens_and_adds_cash():
    p = Portfolio.fresh()
    p.buy("opus", kt=100, price_chf_per_kt=0.4)
    p.sell("opus", kt=50, price_chf_per_kt=0.5)
    assert p.holding("opus").ktokens == 50
    # started with 1000 - 40 = 960, + 25 from sell = 985
    assert p.cash_chf == pytest.approx(985.0)


def test_cannot_sell_more_than_held():
    p = Portfolio.fresh()
    p.buy("opus", kt=10, price_chf_per_kt=0.4)
    with pytest.raises(ValueError):
        p.sell("opus", kt=50, price_chf_per_kt=0.5)


def test_pnl_at_start_is_zero():
    p = Portfolio.fresh()
    prices = {"opus": 0.4}
    assert p.pnl_pct(prices) == pytest.approx(0.0)


def test_pnl_reflects_price_moves():
    p = Portfolio.fresh()
    p.buy("opus", kt=100, price_chf_per_kt=0.4)  # spends 40, holds 100kT
    # price moves to 0.5: tokens worth 50, cash 960 -> total 1010 -> +1%
    pnl = p.pnl_pct({"opus": 0.5})
    assert pnl == pytest.approx(1.0)


def test_serialize_roundtrip():
    p = Portfolio.fresh()
    p.buy("opus", kt=100, price_chf_per_kt=0.4)
    s = p.to_json()
    p2 = Portfolio.from_json(s)
    assert p2.cash_chf == p.cash_chf
    assert p2.day == p.day
    assert p2.holding("opus").ktokens == 100
