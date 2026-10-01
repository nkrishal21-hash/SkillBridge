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
    Robustly handles Base64 '+' vs space encoding, comma formatting, and
    decimal precision variants (.0 vs .00 vs int) from eSewa gateway.
    """
    signed_fields_str = decoded_payload.get("signed_field_names", "")
    returned_signature = str(decoded_payload.get("signature", "")).strip().replace(" ", "+")

    if not signed_fields_str or not returned_signature:
        print("[SkillBridge Payment] verify_esewa_callback: Missing signed_field_names or signature")
        return False

    key = secret_key or current_app.config.get("ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")

    # Build the message string exactly from the listed signed_field_names
    field_names = [f.strip() for f in signed_fields_str.split(",") if f.strip()]
    message_parts = [f"{f}={decoded_payload.get(f, '')}" for f in field_names]
    message = ",".join(message_parts)

    def _calc_sig(msg: str) -> str:
        mac = hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode("utf-8")

    # 1. Primary check: exact fields as provided in payload
    expected_signature = _calc_sig(message)
    if hmac.compare_digest(expected_signature, returned_signature):
        print("[SkillBridge Payment] Signature verification passed (exact match)")
        return True

    # 2. Tolerant check for total_amount variations (commas, .0, .00, int)
    raw_amount = str(decoded_payload.get("total_amount", "")).strip()
    clean_amt = raw_amount.replace(",", "")

    amt_candidates = [clean_amt]
    try:
        amt_float = float(clean_amt)
        amt_candidates.extend([
            f"{amt_float:.2f}",
            f"{amt_float:.1f}",
            str(int(amt_float)) if amt_float.is_integer() else None,
        ])
    except (ValueError, TypeError):
        pass

    for candidate in [c for c in amt_candidates if c]:
        test_parts = []
        for f in field_names:
            val = candidate if f == "total_amount" else str(decoded_payload.get(f, ""))
            test_parts.append(f"{f}={val}")
        test_msg = ",".join(test_parts)
        test_sig = _calc_sig(test_msg)
        if hmac.compare_digest(test_sig, returned_signature):
            print(f"[SkillBridge Payment] Signature verification passed with total_amount candidate '{candidate}'")
            return True

    print(f"[SkillBridge Payment] Signature verification failed! Raw message: '{message}', Expected: '{expected_signature}', Returned: '{returned_signature}'")
    return False


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

    clean_amount = str(total_amount).replace(",", "").strip()
    try:
        clean_amount = f"{float(clean_amount):.2f}"
    except (ValueError, TypeError):
        pass

    params = {
        "product_code": product_code,
        "total_amount": clean_amount,
        "transaction_uuid": transaction_uuid,
    }

    try:
        print(f"[SkillBridge Payment] Querying eSewa status API: {url} params={params}")
        response = requests.get(url, params=params, timeout=10)
        print(f"[SkillBridge Payment] eSewa status API HTTP {response.status_code}: {response.text}")
        if response.status_code == 200:
            return response.json()
        
        # If 400 Bad Request, try with 1 decimal place format (.0)
        try:
            alt_amount = f"{float(clean_amount):.1f}"
            if alt_amount != clean_amount:
                params["total_amount"] = alt_amount
                alt_resp = requests.get(url, params=params, timeout=10)
                if alt_resp.status_code == 200:
                    return alt_resp.json()
        except Exception:
            pass

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

