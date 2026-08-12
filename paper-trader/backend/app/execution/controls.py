"""Strict holder-side execution of durable account controls."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import AccountExecutionCommand, OrderJournal
from app.engine.execution_lifecycle import ExecutionLifecycleStore
from app.execution.leases import LeaseRepository, LeaseToken


def apply_control(repository: LeaseRepository, token: LeaseToken, runner, command,
                  session_factory) -> str:
    operation = command.kind.removeprefix("control_")
    try:
        if operation in {"arm", "disarm"}:
            local_armed = operation == "arm"
        elif operation == "kill":
            runner.kill()
            runner.armed = False
            with session_factory() as session:
                working_journal = session.scalar(select(func.count()).select_from(OrderJournal).where(
                    OrderJournal.owner_id == token.owner_id,
                    OrderJournal.broker_account_id == token.broker_account_id,
                    OrderJournal.deployment_id == runner.deployment_id,
                    OrderJournal.status == "WORKING"))
                unresolved_commands = session.scalar(select(func.count()).select_from(
                    AccountExecutionCommand).where(
                        AccountExecutionCommand.owner_id == token.owner_id,
                        AccountExecutionCommand.broker_account_id == token.broker_account_id,
                        AccountExecutionCommand.command_id != command.command_id,
                        ~AccountExecutionCommand.kind.like("control_%"),
                        AccountExecutionCommand.state.in_((
                            "prepared", "sent_unknown", "acknowledged", "processing"))))
                connection = getattr(runner.broker, "connection", None)
                unresolved_lifecycle = []
                if connection is not None:
                    unresolved_lifecycle = ExecutionLifecycleStore(
                        session, owner_id=token.owner_id,
                        broker_account_id=token.broker_account_id).unresolved_entries(
                            runner.deployment_id, runner.broker.account.external_account_id,
                            connection.scope, broker=connection.broker)
            if (list(runner.broker.open_positions())
                    or dict(getattr(runner.broker, "_inflight", {}))
                    or dict(getattr(runner.broker, "_pending_entries", {}))
                    or working_journal or unresolved_commands or unresolved_lifecycle):
                repository.complete_control_with_projection(
                    token, command.command_id, deployment_id=runner.deployment_id,
                    armed=False, success=False)
                raise RuntimeError("kill was partial; positions or working entries remain")
            local_armed = False
        else:
            raise RuntimeError("unsupported holder control")
        repository.complete_control_with_projection(
            token, command.command_id, deployment_id=runner.deployment_id, armed=local_armed)
        runner.armed = local_armed
        return "resolved"
    except Exception as exc:
        try:
            repository.complete_control(token, command.command_id, success=False)
        except Exception:
            pass
        raise
