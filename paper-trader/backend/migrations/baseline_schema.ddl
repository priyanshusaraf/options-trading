-- Baseline execution-database schema, generated from app/db/models.py at
-- Alembic revision 0001 (2026-08-02). DO NOT EDIT BY HAND.
--
-- Extension is .ddl, NOT .sql, and that is deliberate: scripts/deploy.sh excludes
-- '*.sql' from the rsync (it is how ledger backups are kept off the VPS), and its
-- Guard 0 asserts the exclude list is strictly pairs of `--exclude PATTERN`. Adding
-- an --include for this one file would mean widening a guard whose actual job is
-- protecting the production .env and the live database. Renaming the file was the
-- cheaper side of that trade. Do not "correct" this back to .sql.
--
-- This is the pre-Alembic floor. tests/test_schema_migrations.py executes it to
-- build a synthetic legacy database, migrates it to head, and asserts the result
-- matches what the ORM models produce. Regenerating it would defeat that check:
-- if the models move ahead of this file, the difference must be an Alembic
-- revision, not an edit here.

CREATE TABLE backtest_results (
	id INTEGER NOT NULL, 
	run_id INTEGER NOT NULL, 
	instrument_key VARCHAR(48) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	segment VARCHAR(12) NOT NULL, 
	strategy_key VARCHAR(64) NOT NULL, 
	interval VARCHAR(12) NOT NULL, 
	trades INTEGER NOT NULL, 
	wins INTEGER NOT NULL, 
	win_rate FLOAT NOT NULL, 
	profit_factor FLOAT, 
	max_drawdown_pct FLOAT NOT NULL, 
	return_pct FLOAT NOT NULL, 
	net_pnl FLOAT NOT NULL, 
	gross_pnl FLOAT NOT NULL, 
	charges FLOAT NOT NULL, 
	expectancy FLOAT NOT NULL, 
	cagr FLOAT, 
	calmar FLOAT, 
	consistency FLOAT, 
	sharpe FLOAT, 
	max_consec_losses INTEGER NOT NULL, 
	time_underwater_pct FLOAT NOT NULL, 
	worst_trade_pnl FLOAT NOT NULL, 
	worst_mae_pct FLOAT NOT NULL, 
	notional FLOAT NOT NULL, 
	lots INTEGER NOT NULL, 
	affordable BOOLEAN NOT NULL, 
	option_cost FLOAT NOT NULL, 
	open_at_end BOOLEAN NOT NULL, 
	win_rate_realised FLOAT NOT NULL, 
	return_pct_realised FLOAT NOT NULL, 
	bh_return_pct FLOAT, 
	first_ts INTEGER NOT NULL, 
	last_ts INTEGER NOT NULL, 
	effective_days INTEGER NOT NULL, 
	clamped BOOLEAN NOT NULL, 
	bars INTEGER NOT NULL, 
	curve_json TEXT NOT NULL, 
	bh_curve_json TEXT NOT NULL, 
	trades_json TEXT NOT NULL, 
	error VARCHAR(400) NOT NULL, 
	premium_trades INTEGER NOT NULL, 
	premium_win_rate FLOAT NOT NULL, 
	premium_net_pnl FLOAT NOT NULL, 
	premium_return_pct FLOAT NOT NULL, 
	premium_profit_factor FLOAT, 
	premium_max_drawdown_pct FLOAT NOT NULL, 
	premium_expectancy FLOAT NOT NULL, 
	premium_charges FLOAT NOT NULL, 
	premium_trades_json TEXT NOT NULL, 
	premium_error VARCHAR(200) NOT NULL, 
	params_hash VARCHAR(64) NOT NULL, 
	last_candle_ts INTEGER NOT NULL, 
	schema_version INTEGER NOT NULL, 
	from_cache BOOLEAN NOT NULL, 
	computed_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE backtest_runs (
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	scope VARCHAR(16) NOT NULL, 
	intervals VARCHAR(128) NOT NULL, 
	capital FLOAT NOT NULL, 
	total INTEGER NOT NULL, 
	done INTEGER NOT NULL, 
	note VARCHAR(400) NOT NULL, 
	window VARCHAR(64) NOT NULL, 
	instruments VARCHAR(400) NOT NULL, 
	strategies VARCHAR(400) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE capital_state (
	id INTEGER NOT NULL, 
	initial_capital FLOAT NOT NULL, 
	cash FLOAT NOT NULL, 
	realized_pnl FLOAT NOT NULL, 
	account_baseline FLOAT, 
	anchored_at DATETIME, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE daily_account_snapshot (
	day VARCHAR(10) NOT NULL, 
	account_net FLOAT NOT NULL, 
	account_available FLOAT NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (day)
);
CREATE TABLE earnings_events (
	symbol VARCHAR(48) NOT NULL, 
	event_date DATE NOT NULL, 
	purpose VARCHAR(128) NOT NULL, 
	fetched_at DATETIME NOT NULL, 
	resolved_at DATETIME, 
	PRIMARY KEY (symbol)
);
CREATE TABLE equity_snapshots (
	id INTEGER NOT NULL, 
	time DATETIME NOT NULL, 
	equity FLOAT NOT NULL, 
	cash FLOAT NOT NULL, 
	invested FLOAT NOT NULL, 
	realized_pnl FLOAT NOT NULL, 
	open_count INTEGER NOT NULL, 
	segment VARCHAR(16), 
	strategy_key VARCHAR(64), 
	PRIMARY KEY (id)
);
CREATE TABLE generated_strategies (
	"key" VARCHAR(64) NOT NULL, 
	composition_json TEXT NOT NULL, 
	source TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY ("key")
);
CREATE TABLE instrument_state (
	instrument_key VARCHAR(32) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	live_interval VARCHAR(12) NOT NULL, 
	entries_blocked BOOLEAN NOT NULL, 
	strategy_key VARCHAR(64), 
	priority_flag BOOLEAN NOT NULL, 
	product VARCHAR(16) NOT NULL, 
	overtrade_flag BOOLEAN NOT NULL, 
	PRIMARY KEY (instrument_key)
);
CREATE TABLE option_data (
	id INTEGER NOT NULL, 
	instrument_key VARCHAR(32) NOT NULL, 
	ts DATETIME NOT NULL, 
	expiry DATE NOT NULL, 
	strike FLOAT NOT NULL, 
	option_type VARCHAR(4) NOT NULL, 
	tradingsymbol VARCHAR(64) NOT NULL, 
	spot FLOAT NOT NULL, 
	ltp FLOAT NOT NULL, 
	bid FLOAT NOT NULL, 
	ask FLOAT NOT NULL, 
	oi INTEGER NOT NULL, 
	volume INTEGER NOT NULL, 
	iv FLOAT, 
	delta FLOAT, 
	PRIMARY KEY (id)
);
CREATE TABLE order_journal (
	id INTEGER NOT NULL, 
	order_id VARCHAR(32), 
	tradingsymbol VARCHAR(64) NOT NULL, 
	instrument_key VARCHAR(64) NOT NULL, 
	side VARCHAR(8) NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	intent VARCHAR(8) NOT NULL, 
	qty INTEGER NOT NULL, 
	context_json TEXT, 
	status VARCHAR(12) NOT NULL, 
	resolution VARCHAR(24), 
	filled_qty INTEGER NOT NULL, 
	avg_price FLOAT NOT NULL, 
	placed_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE positions (
	id INTEGER NOT NULL, 
	instrument_key VARCHAR(32) NOT NULL, 
	direction VARCHAR(8) NOT NULL, 
	option_type VARCHAR(4) NOT NULL, 
	tradingsymbol VARCHAR(64) NOT NULL, 
	exchange VARCHAR(8) NOT NULL, 
	segment VARCHAR(16) NOT NULL, 
	strategy_key VARCHAR(64), 
	strike FLOAT NOT NULL, 
	expiry DATE NOT NULL, 
	lot_size INTEGER NOT NULL, 
	qty INTEGER NOT NULL, 
	entry_premium FLOAT NOT NULL, 
	entry_charges FLOAT NOT NULL, 
	entry_cost FLOAT NOT NULL, 
	entry_spot FLOAT NOT NULL, 
	entry_time DATETIME NOT NULL, 
	entry_reason VARCHAR(400) NOT NULL, 
	stop_price FLOAT NOT NULL, 
	target_price FLOAT NOT NULL, 
	entry_sl_pct FLOAT, 
	entry_tp_pct FLOAT, 
	last_premium FLOAT NOT NULL, 
	last_spot FLOAT NOT NULL, 
	last_mark_time DATETIME, 
	high_water_premium FLOAT NOT NULL, 
	mfe FLOAT NOT NULL, 
	mae FLOAT NOT NULL, 
	reinforcement_count INTEGER NOT NULL, 
	last_reinforce_time DATETIME, 
	held_overnight BOOLEAN NOT NULL, 
	overnight_pnl FLOAT NOT NULL, 
	session_close_premium FLOAT NOT NULL, 
	last_squareoff_date DATE, 
	manual_target BOOLEAN NOT NULL, 
	no_take_profit BOOLEAN NOT NULL, 
	gtt_trigger_id VARCHAR(32), 
	entry_atr FLOAT, 
	ratchet_hw FLOAT, 
	spot_stop FLOAT, 
	ratchet_last_bar_ts DATETIME, 
	mode VARCHAR(8) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE runtime_config (
	"key" VARCHAR(64) NOT NULL, 
	value VARCHAR(64) NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY ("key")
);
CREATE TABLE signal_events (
	id INTEGER NOT NULL, 
	time DATETIME NOT NULL, 
	instrument_key VARCHAR(32) NOT NULL, 
	signal VARCHAR(16) NOT NULL, 
	z FLOAT NOT NULL, 
	slope FLOAT NOT NULL, 
	close FLOAT NOT NULL, 
	acted BOOLEAN NOT NULL, 
	note VARCHAR(400) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE strategy_lifecycle (
	id INTEGER NOT NULL, 
	strategy_key VARCHAR(64) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	source VARCHAR(12) NOT NULL, 
	deployed_watchlist_id INTEGER, 
	last_dsr FLOAT, 
	note TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(deployed_watchlist_id) REFERENCES watchlists (id)
);
CREATE TABLE trades (
	id INTEGER NOT NULL, 
	instrument_key VARCHAR(32) NOT NULL, 
	direction VARCHAR(8) NOT NULL, 
	option_type VARCHAR(4) NOT NULL, 
	tradingsymbol VARCHAR(64) NOT NULL, 
	exchange VARCHAR(8) NOT NULL, 
	segment VARCHAR(16) NOT NULL, 
	strategy_key VARCHAR(64), 
	strike FLOAT NOT NULL, 
	expiry DATE NOT NULL, 
	qty INTEGER NOT NULL, 
	entry_premium FLOAT NOT NULL, 
	entry_cost FLOAT NOT NULL, 
	entry_spot FLOAT NOT NULL, 
	entry_time DATETIME NOT NULL, 
	exit_premium FLOAT NOT NULL, 
	exit_charges FLOAT NOT NULL, 
	exit_spot FLOAT NOT NULL, 
	exit_time DATETIME NOT NULL, 
	exit_reason VARCHAR(32) NOT NULL, 
	gross_pnl FLOAT NOT NULL, 
	charges_total FLOAT NOT NULL, 
	net_pnl FLOAT NOT NULL, 
	return_pct FLOAT NOT NULL, 
	holding_minutes FLOAT NOT NULL, 
	win BOOLEAN NOT NULL, 
	held_overnight BOOLEAN NOT NULL, 
	overnight_pnl FLOAT NOT NULL, 
	intraday_pnl FLOAT NOT NULL, 
	reinforcements INTEGER NOT NULL, 
	mode VARCHAR(8) NOT NULL, 
	exit_price_estimated BOOLEAN NOT NULL, 
	mfe FLOAT NOT NULL, 
	mae FLOAT NOT NULL, 
	build_sha VARCHAR(64), 
	PRIMARY KEY (id)
);
CREATE TABLE universe_instruments (
	"key" VARCHAR(48) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	segment VARCHAR(12) NOT NULL, 
	spot_exchange VARCHAR(12) NOT NULL, 
	spot_symbol VARCHAR(64) NOT NULL, 
	option_name VARCHAR(64) NOT NULL, 
	lot_size INTEGER NOT NULL, 
	strike_step FLOAT NOT NULL, 
	priority INTEGER NOT NULL, 
	has_options BOOLEAN NOT NULL, 
	source VARCHAR(8) NOT NULL, 
	on_home BOOLEAN NOT NULL, 
	active BOOLEAN NOT NULL, 
	mock_spot FLOAT NOT NULL, 
	mock_vol FLOAT NOT NULL, 
	PRIMARY KEY ("key")
);
CREATE TABLE watchlist_membership (
	instrument_key VARCHAR(48) NOT NULL, 
	watchlist_id INTEGER NOT NULL, 
	added_at DATETIME NOT NULL, 
	PRIMARY KEY (instrument_key), 
	FOREIGN KEY(watchlist_id) REFERENCES watchlists (id)
);
CREATE TABLE watchlists (
	id INTEGER NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	strategy_key VARCHAR(64) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	interval VARCHAR(12), 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
CREATE INDEX ix_backtest_results_instrument_key ON backtest_results (instrument_key);
CREATE INDEX ix_backtest_results_interval ON backtest_results (interval);
CREATE INDEX ix_backtest_results_run_id ON backtest_results (run_id);
CREATE INDEX ix_backtest_results_strategy_key ON backtest_results (strategy_key);
CREATE INDEX ix_equity_snapshots_time ON equity_snapshots (time);
CREATE INDEX ix_option_data_instrument_key ON option_data (instrument_key);
CREATE INDEX ix_option_data_ts ON option_data (ts);
CREATE INDEX ix_order_journal_order_id ON order_journal (order_id);
CREATE INDEX ix_order_journal_status ON order_journal (status);
CREATE INDEX ix_positions_instrument_key ON positions (instrument_key);
CREATE INDEX ix_signal_events_instrument_key ON signal_events (instrument_key);
CREATE INDEX ix_signal_events_time ON signal_events (time);
CREATE UNIQUE INDEX ix_strategy_lifecycle_strategy_key ON strategy_lifecycle (strategy_key);
CREATE INDEX ix_trades_exit_time ON trades (exit_time);
CREATE INDEX ix_trades_instrument_key ON trades (instrument_key);
CREATE INDEX ix_watchlist_membership_watchlist_id ON watchlist_membership (watchlist_id);
