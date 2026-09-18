"""
app/payments/utils.py — eSewa ePay v2 Integration Utilities
Handles HMAC-SHA256 signature generation, callback signature validation,
and defense-in-depth status checking against eSewa's transaction status API.
"""

import hmac
import hashlib
import base64
import requests
from flask import current_app


def build_esewa_signature(total_amount: str, transaction_uuid: str, product_code: str, secret_key: str = None) -> str:
    """
    Generate an HMAC-SHA256 base64-encoded signature for an eSewa initiation request.
    Message format: "total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    """
    key = secret_key or current_app.config.get("ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")
    message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    
    mac = hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    )
    return base64.b64encode(mac.digest()).decode("utf-8")


def verify_esewa_callback(decoded_payload: dict, secret_key: str = None) -> bool:
    """
    Verify the callback signature from eSewa's ?data=<base64> response.
    Reconstructs the message in the exact order specified by signed_field_names.
    Uses constant-time comparison (hmac.compare_digest).
    """
    signed_fields_str = decoded_payload.get("signed_field_names", "")
    returned_signature = decoded_payload.get("signature", "")

    if not signed_fields_str or not returned_signature:
        return False

    key = secret_key or current_app.config.get("ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")

    # Build the message string exactly from the listed signed_field_names
    field_names = [f.strip() for f in signed_fields_str.split(",") if f.strip()]
    message_parts = [f"{f}={decoded_payload.get(f, '')}" for f in field_names]
    message = ",".join(message_parts)

    mac = hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    )
    expected_signature = base64.b64encode(mac.digest()).decode("utf-8")

    return hmac.compare_digest(expected_signature, returned_signature)


def check_esewa_status(product_code: str, total_amount: str, transaction_uuid: str) -> dict:
    """
    Call eSewa's status-check API to independently verify transaction completion.
    Endpoint: https://rc.esewa.com.np/api/epay/transaction/status/
    Returns parsed JSON on success, or a dict with status="ERROR" on network failure.
    """
    url = current_app.config.get(
        "ESEWA_STATUS_URL",
        "https://rc.esewa.com.np/api/epay/transaction/status/"
    )
    params = {
        "product_code": product_code,
        "total_amount": total_amount,
        "transaction_uuid": transaction_uuid,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {
            "status": "ERROR",
            "message": f"eSewa status check returned HTTP {response.status_code}",
            "response": response.text,
        }
    except requests.exceptions.RequestException as exc:
        print(f"[SkillBridge Payment] eSewa status check error: {exc}")
        return {
            "status": "ERROR",
            "message": str(exc),
        }
