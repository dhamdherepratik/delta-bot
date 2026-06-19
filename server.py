import hmac
import logging
import os

from flask import Flask, jsonify, request

from main import handle_signal


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = Flask(__name__)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


def _extract_signal():
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        return payload.get("signal") or payload.get("message") or ""
    return request.get_data(as_text=True).strip()


@app.get("/")
def home():
    return jsonify(status="running", message="TradingView webhook is active")


@app.post("/webhook/<secret>")
def webhook(secret):
    if not WEBHOOK_SECRET or not hmac.compare_digest(secret, WEBHOOK_SECRET):
        return jsonify(status="error", message="Not found"), 404

    signal = _extract_signal()
    try:
        result = handle_signal(signal)
        return jsonify(status="ok", received=signal, result=result)
    except ValueError as exc:
        app.logger.warning("Rejected webhook: %s", exc)
        return jsonify(status="error", message=str(exc)), 400
    except Exception:
        app.logger.exception("Order processing failed")
        return jsonify(status="error", message="Order processing failed"), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
