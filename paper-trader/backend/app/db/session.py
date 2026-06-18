"""Engine + session factory + one-time schema/seed init."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.instruments import all_instruments
from app.db.models import Base, CapitalState, InstrumentState

_settings = get_settings()
engine = create_engine(
    f"sqlite:///{_settings.db_path}",
    future=True,
    connect_args={"check_same_thread": False},  # engine task + API threads
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")   # concurrent reads while engine writes
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)


def init_db(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = get_settings()
    with SessionLocal() as sess:
        if sess.get(CapitalState, 1) is None:
            sess.add(CapitalState(id=1, initial_capital=s.initial_capital,
                                  cash=s.initial_capital, realized_pnl=0.0))
        for inst in all_instruments():
            if sess.get(InstrumentState, inst.key) is None:
                sess.add(InstrumentState(instrument_key=inst.key, enabled=True))
        sess.commit()
