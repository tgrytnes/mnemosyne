import logging
import os
import signal
import sys

import click
import psycopg2

from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent
from mnemosyne.alexandria.communication_intents import PMIntentQueue
from mnemosyne.alexandria.message_outbox import MessageOutbox
from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper
from mnemosyne.argus.scout.monitor_agent import ProposalQueue
from mnemosyne.hermes.telegram_poller import TelegramApiClient, TelegramOutboxPoller

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

shutdown_flag = False


def _handle_signal(_signum, _frame) -> None:
    global shutdown_flag
    shutdown_flag = True


class HermesConfig:
    def __init__(self) -> None:
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.default_chat_id = os.getenv("TELEGRAM_USER_ID", "").strip() or None
        self.poll_interval_seconds = int(os.getenv("TELEGRAM_POLL_INTERVAL_SECONDS", "30"))
        self.reply_timeout_seconds = int(os.getenv("TELEGRAM_REPLY_TIMEOUT_SECONDS", "25"))
        self.send_limit = int(os.getenv("TELEGRAM_SEND_LIMIT", "10"))
        self.message_outbox_path = os.getenv("MESSAGE_OUTBOX_PATH", "message_outbox.db")
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB", "mnemosyne")
        self.postgres_user = os.getenv("POSTGRES_USER", "postgres")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "")


def _gatekeeper_config_from_env() -> GatekeeperConfig:
    auto_reject = os.getenv("GATEKEEPER_AUTO_REJECT_THRESHOLD")
    auto_approve = os.getenv("GATEKEEPER_AUTO_APPROVE_THRESHOLD")
    rollback_days = os.getenv("GATEKEEPER_ROLLBACK_WINDOW_DAYS")

    def _maybe_float(value: str | None, fallback: float) -> float:
        if value is None:
            return fallback
        return float(value)

    def _maybe_int(value: str | None, fallback: int) -> int:
        if value is None:
            return fallback
        return int(value)

    defaults = GatekeeperConfig()
    return GatekeeperConfig(
        auto_reject_threshold=_maybe_float(auto_reject, defaults.auto_reject_threshold),
        auto_approve_threshold=_maybe_float(auto_approve, defaults.auto_approve_threshold),
        rollback_window_days=_maybe_int(rollback_days, defaults.rollback_window_days),
    )


def _connect_postgres(config: HermesConfig):
    return psycopg2.connect(
        host=config.postgres_host,
        port=config.postgres_port,
        dbname=config.postgres_db,
        user=config.postgres_user,
        password=config.postgres_password,
    )


def _build_project_manager_agent(db_conn, outbox: MessageOutbox) -> ProjectManagerAgent:
    proposal_queue = ProposalQueue(db_conn)
    intent_queue = PMIntentQueue(db_conn)
    gatekeeper = SQLProjectGatekeeper(
        db_conn,
        proposal_queue=proposal_queue,
        intent_queue=intent_queue,
        config=_gatekeeper_config_from_env(),
    )
    return ProjectManagerAgent(
        db_conn=db_conn,
        message_outbox=outbox,
        gatekeeper=gatekeeper,
        intent_queue=intent_queue,
    )


def run_poller(*, once: bool) -> None:
    config = HermesConfig()
    if not config.bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is required to run the Hermes poller.")
        sys.exit(1)

    message_outbox = MessageOutbox(config.message_outbox_path)
    postgres_conn = None
    try:
        postgres_conn = _connect_postgres(config)
        agent = _build_project_manager_agent(postgres_conn, message_outbox)
        poller = TelegramOutboxPoller(
            message_outbox,
            TelegramApiClient(config.bot_token),
            default_chat_id=config.default_chat_id,
            poll_interval_seconds=config.poll_interval_seconds,
            reply_timeout_seconds=config.reply_timeout_seconds,
            send_limit=config.send_limit,
            response_router=agent.handle_outbox_response,
        )

        if once:
            poller.deliver_pending()
            poller.poll_replies()
        else:
            logger.info("Hermes poller started (interval=%ss)", config.poll_interval_seconds)
            poller.run_forever(stop_signal=lambda: shutdown_flag)
    finally:
        message_outbox.close()
        if postgres_conn:
            postgres_conn.close()


@click.command("hermes")
@click.option(
    "--once",
    is_flag=True,
    help="Run a single delivery + reply poll cycle and exit.",
)
def hermes_cli(once: bool):
    """Mnemosyne Hermes outbox poller"""
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    run_poller(once=once)
