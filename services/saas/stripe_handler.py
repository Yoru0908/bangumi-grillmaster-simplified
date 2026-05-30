"""Stripe integration: Checkout Sessions + Webhook handler."""

from __future__ import annotations

import stripe
from loguru import logger

from settings import settings

# Price config — minutes per plan
PLANS = {
    "taster":     {"minutes": 60,  "amount_cny": 12,  "name": "尝鲜 60分钟"},
    "popular":    {"minutes": 150, "amount_cny": 25,  "name": "常用 150分钟"},
    "bulk":       {"minutes": 360, "amount_cny": 50,  "name": "畅看 360分钟"},
    "starter_sub": {"minutes": 120, "amount_cny": 15, "name": "入门包月 120min/月", "recurring": "month"},
    "standard_sub": {"minutes": 300, "amount_cny": 29, "name": "标准包月 300min/月", "recurring": "month"},
    "pro_sub":      {"minutes": 600, "amount_cny": 49, "name": "全追包月 600min/月", "recurring": "month"},
}

# Convert CNY to smallest currency unit (分 for RMB via Stripe)
def _cny_to_fen(amount: float) -> int:
    return int(amount * 100)


def create_checkout_session(
    *,
    plan_key: str,
    user_email: str,
    user_id: str,
    base_url: str,
) -> str:
    """Create a Stripe Checkout Session and return the URL."""
    stripe.api_key = settings.stripe_secret_key
    plan = PLANS[plan_key]
    is_subscription = "recurring" in plan

    if is_subscription:
        # Build price data inline for simplicity (test mode)
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
    """Process Stripe webhook event. Returns {status, user_id, minutes}."""
    stripe.api_key = settings.stripe_secret_key

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret or ""
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning(f"Stripe webhook signature invalid: {e}")
        return {"status": "invalid_signature"}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        plan_key = session.get("metadata", {}).get("plan_key", "")
        minutes = int(session.get("metadata", {}).get("minutes", "0"))
        user_id = session.get("client_reference_id", "")
        logger.info(
            f"Stripe payment success: user={user_id} "
            f"plan={plan_key} minutes={minutes}"
        )
        return {"status": "ok", "user_id": user_id, "minutes": minutes}

    # For subscription events, we need to handle differently
    if event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        # Get subscription metadata from the subscription
        subscription_id = invoice.get("subscription")
        if subscription_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            metadata = sub.get("metadata", {})
            plan_key = metadata.get("plan_key", "")
            minutes = int(metadata.get("minutes", "0"))
            user_id = sub.get("client_reference_id", "")
            logger.info(
                f"Stripe subscription invoice paid: user={user_id} "
                f"plan={plan_key} minutes={minutes}"
            )
            return {"status": "ok", "user_id": user_id, "minutes": minutes}

    return {"status": "unhandled_event", "type": event["type"]}
