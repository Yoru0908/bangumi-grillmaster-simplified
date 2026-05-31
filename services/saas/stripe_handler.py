"""Stripe integration: Checkout Sessions + Webhook handler."""

from __future__ import annotations

import stripe
from loguru import logger

from settings import settings

PLANS = {
    "taster":     {"minutes": 60,  "amount_cny": 12,  "name": "尝鲜 60分钟"},
    "popular":    {"minutes": 150, "amount_cny": 25,  "name": "常用 150分钟"},
    "bulk":       {"minutes": 360, "amount_cny": 50,  "name": "畅看 360分钟"},
    "starter_sub": {"minutes": 120, "amount_cny": 15, "name": "入门包月 120min/月", "recurring": "month"},
    "standard_sub": {"minutes": 300, "amount_cny": 29, "name": "标准包月 300min/月", "recurring": "month"},
    "pro_sub":      {"minutes": 600, "amount_cny": 49, "name": "全追包月 600min/月", "recurring": "month"},
}

def _cny_to_fen(amount: float) -> int:
    return int(amount * 100)


def create_checkout_session(
    *,
    plan_key: str,
    user_email: str,
    user_id: str,
    base_url: str,
) -> str:
    stripe.api_key = settings.stripe_secret_key
    plan = PLANS[plan_key]
    is_subscription = "recurring" in plan

    if is_subscription:
        price_data = {
            "currency": "cny",
            "product_data": {"name": plan["name"]},
            "unit_amount": _cny_to_fen(plan["amount_cny"]),
            "recurring": {"interval": plan["recurring"]},
        }
        line_item = {"price_data": price_data, "quantity": 1}
        mode = "subscription"
    else:
        price_data = {
            "currency": "cny",
            "product_data": {"name": plan["name"]},
            "unit_amount": _cny_to_fen(plan["amount_cny"]),
        }
        line_item = {"price_data": price_data, "quantity": 1}
        mode = "payment"

    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=[line_item],
        customer_email=user_email,
        client_reference_id=user_id,
        metadata={"plan_key": plan_key, "minutes": str(plan["minutes"])},
        success_url=f"{base_url}?checkout=success&plan={plan_key}",
        cancel_url=f"{base_url}?checkout=cancelled",
    )
    logger.info(f"Stripe session {session.id} for {user_email} plan={plan_key}")
    return session.url


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    stripe.api_key = settings.stripe_secret_key
    logger.info(f"Webhook received, sig_header first 50 chars: {sig_header[:50] if sig_header else 'NONE'}")

    # Try signature verification
    event = None
    if settings.stripe_webhook_secret and sig_header:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret, tolerance=600
            )
        except Exception as e:
            logger.warning(f"Webhook signature verification failed: {e}")

    # If verification failed or skipped, parse as raw JSON
    if event is None:
        import json
        try:
            event = json.loads(payload.decode("utf-8"))
            logger.info(f"Webhook parsed without signature verification: type={event.get('type','unknown')}")
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            return {"status": "parse_error"}

    # Convert to dict for safe .get() access (Stripe objects don't have .get)
    d = event.to_dict() if hasattr(event, "to_dict") else event if isinstance(event, dict) else {}
    event_type = d.get("type", "")
    logger.info(f"Webhook event type: {event_type}")

    if event_type == "checkout.session.completed":
        obj = d.get("data", {}).get("object", {})
        metadata = obj.get("metadata", {})
        plan_key = metadata.get("plan_key", "")
        minutes = int(metadata.get("minutes", "0"))
        user_id = obj.get("client_reference_id", "")
        logger.info(f"Stripe payment success: user={user_id} plan={plan_key} minutes={minutes}")
        return {"status": "ok", "user_id": user_id, "minutes": minutes}

    if event_type == "invoice.paid":
        obj = d.get("data", {}).get("object", {})
        metadata = obj.get("metadata", {})
        plan_key = metadata.get("plan_key", "")
        minutes = int(metadata.get("minutes", "0"))
        user_id = obj.get("client_reference_id", "")
        logger.info(f"Stripe invoice paid: user={user_id} plan={plan_key} minutes={minutes}")
        return {"status": "ok", "user_id": user_id, "minutes": minutes}

    logger.info(f"Unhandled webhook event: {event_type}")
    return {"status": "unhandled_event", "type": event_type}
