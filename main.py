import logging
import os
import threading

from delta_rest_client import DeltaRestClient, OrderType


logger = logging.getLogger(__name__)


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


delta_client = DeltaRestClient(
    base_url=os.getenv("DELTA_BASE_URL", "https://cdn-ind.testnet.deltaex.org"),
    api_key=_required_env("DELTA_API_KEY"),
    api_secret=_required_env("DELTA_API_SECRET"),
)

PRODUCT_ID = int(os.getenv("DELTA_PRODUCT_ID", "84"))
ORDER_SIZE = int(os.getenv("DELTA_ORDER_SIZE", "1"))

# Render runs this service with one Gunicorn worker. This lock also prevents two
# alerts handled by different threads from changing the position simultaneously.
_order_lock = threading.Lock()
current_position = None


def _place_market_order(side, reduce_only=False):
    return delta_client.place_order(
        product_id=PRODUCT_ID,
        size=ORDER_SIZE,
        side=side,
        order_type=OrderType.MARKET,
        reduce_only="true" if reduce_only else "false",
    )


def close_position():
    global current_position

    if current_position is None:
        return None

    side = "sell" if current_position == "LONG" else "buy"
    logger.info("Closing %s position", current_position)
    response = _place_market_order(side, reduce_only=True)
    current_position = None
    return response


def _open_position(position):
    global current_position

    if current_position == position:
        return {"action": "ignored", "reason": f"already {position.lower()}"}

    if current_position is not None:
        close_position()

    side = "buy" if position == "LONG" else "sell"
    logger.info("Opening %s position", position)
    response = _place_market_order(side)
    current_position = position
    return {"action": position.lower(), "order": response}


def handle_signal(signal):
    if not isinstance(signal, str) or not signal.strip():
        raise ValueError("Signal is empty")

    normalized = " ".join(signal.strip().upper().split())
    positions = {
        "UT LONG": "LONG",
        "BUY": "LONG",
        "LONG": "LONG",
        "UT SHORT": "SHORT",
        "SELL": "SHORT",
        "SHORT": "SHORT",
    }
    position = positions.get(normalized)
    if position is None:
        raise ValueError(f"Unknown signal: {signal!r}")

    with _order_lock:
        return _open_position(position)
