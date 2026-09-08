"""Resolve a saved provider row through replayed, fresh historical authority."""
from __future__ import annotations

from app.monitoring import input_producer
from app.monitoring.watchlist_config import TIMEFRAMES
from research.data.historical_capture import PURPOSE


def resolve_provider_watchlist_instrument(execution_session, research_session, *, requested,
        assignment_spec, policy, manifest_address, now):
    """The caller supplies an address; retained facts establish the actual mapping."""
    from app.monitoring.watchlist_store import WatchlistMonitoringConflict
    try:
        input_producer._request(now, TIMEFRAMES[requested.timeframe][0], 1, policy['maximum_age_seconds'], now)
        data = input_producer._dataset(research_session, execution_session, requested.owner_id, manifest_address, now)
        manifest = data._verified_authority.manifest
        historical = data.binding['historical_capture']
        expected = (PURPOSE + requested.project_id, requested.member_key,
            assignment_spec.data_connection_id, TIMEFRAMES[requested.timeframe][0])
        actual = (manifest.purpose, 'PROVIDER_REFERENCE:' + historical['provider_selection_address'],
            historical['connection_id'], data._alignment_fact.resolution_seconds)
        if actual != expected:
            raise ValueError('input does not bind this requested row')
        instrument = data.binding['instrument_address']
        observations = input_producer._terminal(execution_session, data)
        input_producer._terminal_clock(observations, data, instrument, actual[-1], now, policy['maximum_age_seconds'])
        return instrument
    except (ValueError, TypeError, KeyError, AttributeError, LookupError) as exc:
        raise WatchlistMonitoringConflict('Provider-reference binding requires fresh verified mapping provenance for this row.') from exc
