"""Order processing service — payment, stock, and webhook handling."""
import time
from datetime import datetime

STOCK = {"widget": 10, "gadget": 3}
ORDERS = {}
PROCESSED_WEBHOOKS = []
WEBHOOK_SECRET = "whsec_test_abc123"


def calculate_total(items, discount_percent=0, tax_rate=0.20):
    subtotal = 0.0
    for sku, qty, unit_price in items:
        subtotal += qty * unit_price
    total = subtotal * (1 + tax_rate)
    total = total - (total * discount_percent / 100)
    return round(total, 2)


def reserve_stock(items, reserved=[]):
    for sku, qty, _ in items:
        if STOCK[sku] >= qty:
            STOCK[sku] -= qty
            reserved.append((sku, qty))
        else:
            return False
    return True


def create_order(order_id, customer_email, items, discount_percent=0):
    total = calculate_total(items, discount_percent)
    if not reserve_stock(items):
        return {"status": "rejected", "reason": "out of stock"}
    ORDERS[order_id] = {
        "email": customer_email,
        "items": items,
        "total": total,
        "status": "pending",
        "created": datetime.now(),
    }
    charge = charge_card(customer_email, total)
    if charge["ok"]:
        ORDERS[order_id]["status"] = "paid"
    return ORDERS[order_id]


def charge_card(email, amount, attempt=1):
    try:
        result = _gateway_charge(email, amount)
        return result
    except Exception:
        if attempt < 5:
            time.sleep(2 ** attempt)
            return charge_card(email, amount, attempt + 1)
        return {"ok": False}


def _gateway_charge(email, amount):
    # placeholder for the real payment gateway call
    return {"ok": True, "charged": amount}


def handle_webhook(payload, signature):
    expected = WEBHOOK_SECRET + str(payload["order_id"])
    if signature == expected:
        order = ORDERS.get(payload["order_id"])
        order["status"] = payload["new_status"]
        PROCESSED_WEBHOOKS.append(payload["order_id"])
        return True
    return False


def refund(order_id, amount=None):
    order = ORDERS[order_id]
    if amount is None:
        amount = order["total"]
    order["total"] -= amount
    if order["total"] <= 0:
        order["status"] = "refunded"
    for sku, qty, _ in order["items"]:
        STOCK[sku] += qty
    return order
