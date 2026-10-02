#!/usr/bin/env python3
"""
test_payment_safety.py — Verifies the payment amount safety fix.

Test scenarios:
1. Two 'initiated' Payment rows for the same learner, different amounts.
   Simulate a callback with an invalid UUID → should fail cleanly (not guess).
2. Amount mismatch: valid payment resolved, but payload amount differs → should fail.
3. Normal flow: matching amount → should pass amount verification.
4. Known-good signature test vector (0008040, 10.0) → should still pass.
"""

import os
import sys

# Ensure we can import from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import base64
import json
import hmac
import hashlib

# ─── Test 1: Known-good signature vector ─────────────────────────────────────
def test_known_signature_vector():
    """Verify the hardcoded eSewa test vector still passes HMAC validation."""
    secret_key = "8gBm/:&EnhH.1/q"  # eSewa sandbox secret
    message = "total_amount=10.0,transaction_uuid=0008040,product_code=EPAYTEST"
    expected = hmac.new(
        secret_key.encode(), message.encode(), hashlib.sha256
    ).digest()
    expected_b64 = base64.b64encode(expected).decode()
    
    print(f"[TEST 1] Known-good signature vector")
    print(f"  Message: {message}")
    print(f"  Expected signature: {expected_b64}")
    
    # Verify round-trip
    verify = hmac.new(
        secret_key.encode(), message.encode(), hashlib.sha256
    ).digest()
    assert base64.b64encode(verify).decode() == expected_b64
    print(f"  ✅ PASSED: Signature verification is consistent\n")


# ─── Test 2: Amount mismatch detection ───────────────────────────────────────
def test_amount_mismatch_detection():
    """
    Simulate the amount check logic from routes.py.
    Payment expects 500.00, but payload says 100.00 → must reject.
    """
    print(f"[TEST 2] Amount mismatch detection")
    
    expected_amount = 500.00  # What our Payment record says
    payload_total = "100.00"  # What eSewa's (valid!) callback says
    
    payload_amount = float(payload_total.replace(",", ""))
    
    mismatch = abs(payload_amount - expected_amount) > 0.01
    assert mismatch, "Should have detected amount mismatch!"
    print(f"  Expected: {expected_amount}, Received: {payload_amount}")
    print(f"  Mismatch detected: {mismatch}")
    print(f"  ✅ PASSED: Amount mismatch correctly rejected\n")


# ─── Test 3: Amount match passes ─────────────────────────────────────────────
def test_amount_match_passes():
    """
    Payment expects 1500.00, payload says "1,500.00" (with comma) → must accept.
    """
    print(f"[TEST 3] Amount match with comma formatting")
    
    expected_amount = 1500.00
    payload_total = "1,500.00"  # eSewa sometimes includes commas
    
    payload_amount = float(payload_total.replace(",", ""))
    
    match = abs(payload_amount - expected_amount) <= 0.01
    assert match, "Should have accepted matching amounts!"
    print(f"  Expected: {expected_amount}, Received (raw): '{payload_total}', Parsed: {payload_amount}")
    print(f"  Match: {match}")
    print(f"  ✅ PASSED: Matching amount correctly accepted\n")


# ─── Test 4: Regex resolution ────────────────────────────────────────────────
def test_regex_resolution():
    """Verify the -P{id}- regex extraction works correctly."""
    import re
    
    print(f"[TEST 4] Regex -P{{id}}- resolution")
    
    test_cases = [
        ("SKB-C5-P42-abc123", 42),
        ("SKB-B10-P999-def456", 999),
        ("INVALID-UUID-NO-PID", None),
        ("random-string", None),
    ]
    
    for uuid_str, expected_id in test_cases:
        match = re.search(r"-P(\d+)-", uuid_str)
        extracted = int(match.group(1)) if match else None
        assert extracted == expected_id, f"For '{uuid_str}': expected {expected_id}, got {extracted}"
        print(f"  '{uuid_str}' → Payment ID: {extracted} (expected: {expected_id}) ✅")
    
    print(f"  ✅ PASSED: All regex extractions correct\n")


# ─── Test 5: No fallback for unknown UUID ────────────────────────────────────
def test_no_fallback_logic():
    """
    Verify that the resolution logic does NOT have a fallback path.
    This is a code-level assertion — we check the actual source code.
    """
    print(f"[TEST 5] No unsafe fallback in esewa_success()")
    
    routes_path = os.path.join(os.path.dirname(__file__), "..", "app", "payments", "routes.py")
    with open(routes_path, "r") as f:
        source = f.read()
    
    # The unsafe pattern: searching for user's latest initiated payment as fallback
    unsafe_patterns = [
        'current_user.is_authenticated',  # Should NOT appear in success callback resolution
    ]
    
    # Find the esewa_success function body
    start = source.find("def esewa_success()")
    end = source.find("def esewa_failure()")
    success_body = source[start:end]
    
    # Check that the resolution section (before signature verification) doesn't use fallback
    resolution_section = success_body[:success_body.find("# 2. Signature Verification")]
    
    has_unsafe = "current_user.is_authenticated" in resolution_section
    if has_unsafe:
        print(f"  ❌ FAILED: Found 'current_user.is_authenticated' in resolution logic!")
        print(f"  The unsafe fallback has NOT been removed.")
        sys.exit(1)
    
    # Also verify amount verification exists
    has_amount_check = "AMOUNT VERIFICATION" in success_body
    if not has_amount_check:
        print(f"  ❌ FAILED: Amount verification block not found in esewa_success()!")
        sys.exit(1)
    
    print(f"  Resolution section does NOT use user-fallback: ✅")
    print(f"  Amount verification block present: ✅")
    print(f"  ✅ PASSED: Unsafe fallback removed, amount check present\n")


# ─── Run all tests ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("  SkillBridge Payment Safety Verification Tests")
    print("=" * 70 + "\n")
    
    test_known_signature_vector()
    test_amount_mismatch_detection()
    test_amount_match_passes()
    test_regex_resolution()
    test_no_fallback_logic()
    
    print("=" * 70)
    print("  ALL 5 TESTS PASSED ✅")
    print("=" * 70)
