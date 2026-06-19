"""Segment session windows: the live engine must not poll / trade off-hours."""
import datetime as dt

from app.core import market_hours as mh

FRI = "2026-06-19"   # a Friday
SAT = "2026-06-20"   # a Saturday


def at(h, m, date=FRI):
    return dt.datetime.strptime(date, "%Y-%m-%d").replace(hour=h, minute=m, tzinfo=mh.IST)


def test_equity_session_open_midday():
    assert mh.is_open("NSE", at(10, 30))
    assert mh.is_open("NFO", at(14, 0))
    assert mh.is_open("BFO", at(12, 0))


def test_equity_session_closed_outside():
    assert not mh.is_open("NSE", at(9, 0))    # before 9:15
    assert not mh.is_open("NSE", at(16, 0))   # after 15:30


def test_weekend_always_closed():
    assert not mh.is_open("NSE", at(11, 0, SAT))
    assert not mh.is_open("MCX", at(20, 0, SAT))


def test_mcx_runs_late():
    assert mh.is_open("MCX", at(22, 0))       # commodities open till 23:30
    assert not mh.is_open("MCX", at(23, 45))


def test_ncdex_evening_close():
    assert mh.is_open("NCDEX", at(15, 0))
    assert not mh.is_open("NCDEX", at(18, 0))  # agri closes 17:00


def test_any_open():
    # 22:00 Friday: equities closed, MCX open
    assert mh.is_open("MCX", at(22, 0)) and not mh.is_open("NSE", at(22, 0))
