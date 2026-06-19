import logging
import os
import threading
from decimal import Decimal, InvalidOperation

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

# This lock prevents duplicate alerts handled by different threads from changing
# the exchange position simultaneously.
_order_lock = threading.Lock()


def _place_market_order(side, size=ORDER_SIZE, reduce_only=False):
    return delta_client.place_order(
        product_id=PRODUCT_ID,
        size=size,
        side=side,
        order_type=OrderType.MARKET,
        reduce_only="true" if reduce_only else "false",
    )


def _get_open_position():
    payload = delta_client.get_position(PRODUCT_ID)

    if isinstance(payload, dict):
        if "result" in payload:
            payload = payload["result"]
        elif "positions" in payload:
            payload = payload["positions"]

    positions = payload if isinstance(payload, list) else [payload]
    for position in positions:
        if not isinstance(position, dict):
            continue
        if position.get("product_id") not in (None, PRODUCT_ID, str(PRODUCT_ID)):
            continue

        try:
            size = Decimal(str(position.get("size", "0")))
        except (InvalidOperation, TypeError):
            raise RuntimeError("Delta returned an invalid position size")

        if size == 0:
            continue

        side = str(position.get("side", "")).upper()
        if side in {"BUY", "LONG"}:
            direction = "LONG"
        elif side in {"SELL", "SHORT"}:
            direction = "SHORT"
        else:
            direction = "LONG" if size > 0 else "SHORT"

        return {"direction": direction, "size": int(abs(size))}

    return None


def close_position(position=None):
    position = position or _get_open_position()

    if position is None:
        return None

    side = "sell" if position["direction"] == "LONG" else "buy"
    logger.info("Closing %s position", position["direction"])
    return _place_market_order(side, size=position["size"], reduce_only=True)


def _open_position(position):
    current = _get_open_position()

    if current and current["direction"] == position:
        return {"action": "ignored", "reason": f"already {position.lower()}"}

    closed_order = None
    if current is not None:
        closed_order = close_position(current)

    side = "buy" if position == "LONG" else "sell"
    logger.info("Opening %s position", position)
    response = _place_market_order(side)
    return {
        "action": position.lower(),
        "closed_order": closed_order,
        "order": response,
    }


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
