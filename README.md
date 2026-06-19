# TradingView to Delta on Render

This folder is a deployment-safe copy of the webhook service. It accepts the
indicator messages `UT Long` and `UT Short` as plain text and trades on Delta.

## Before deploying

Rotate every Delta key and 2FA recovery code that was stored in the original
project. Never commit the replacement values. Start with Delta testnet and a
small order size.

## Deploy on Render

1. Make this `cloud` folder itself a private GitHub repository. Do not upload
   the parent project because it contains old credentials and virtual environments.
2. In Render, create a new Blueprint and select the repository.
3. Enter the requested `DELTA_API_KEY` and `DELTA_API_SECRET` secret values.
4. After deployment, open the service Environment page and reveal/copy the
   generated `WEBHOOK_SECRET` value.
5. Confirm that `https://YOUR-SERVICE.onrender.com/` returns a running status.

If you create a Web Service manually, leave its root directory blank, use build
command `pip install -r requirements.txt`, and use this start command:

```text
gunicorn --workers 1 --threads 4 --timeout 30 --bind 0.0.0.0:$PORT server:app
```

## TradingView alert

Use this webhook URL, replacing both placeholders:

```text
https://YOUR-SERVICE.onrender.com/webhook/YOUR_WEBHOOK_SECRET
```

Create the alert from `UT Long` or `UT Short`. Keep the indicator's existing
message (`UT Long` or `UT Short`) and select **Once Per Bar Close** if orders
should only be sent after a candle closes.

The endpoint also accepts JSON such as `{"signal":"UT Long"}`, but no Pine
Script change is required for the current plain-text alert messages.

## Operational note

The service checks Delta's live position before acting on every signal, so a
deployment, restart, or manual close does not leave stale position state in the
web process. Choose a Render plan that stays awake; a sleeping instance can
delay a time-sensitive webhook while it starts.
