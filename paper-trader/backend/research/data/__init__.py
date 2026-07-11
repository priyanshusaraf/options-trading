"""HistoricalDataStore — the research plane's versioned, content-addressed local
market-data store. `DataSource` adapters (kite_candles now; option/IV, fundamentals
later) fetch once; series are content-hashed and reused offline so every experiment
binds a reproducible, frozen `Dataset` rather than a live provider call. The inner
optimization loop reads only this store — it never touches a DataSource. (M1.)
"""
