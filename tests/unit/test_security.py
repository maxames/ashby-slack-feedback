"""Unit tests for security utilities (HMAC signature verification)."""

import hmac
import time

import pytest
from flaky import flaky

from app.utils.security import verify_ashby_signature


def test_verify_ashby_signature_valid():
    """Test that valid signatures pass verification."""
    secret = "test_secret"
    body = b'{"action": "test", "data": {}}'
    hex_digest = hmac.new(secret.encode(), body, digestmod="sha256").hexdigest()
    signature = f"sha256={hex_digest}"

    assert verify_ashby_signature(secret, body, signature) is True


def test_verify_ashby_signature_invalid():
    """Test that invalid signatures fail verification."""
    secret = "test_secret"
    body = b'{"action": "test", "data": {}}'
    wrong_signature = "sha256=wrong_signature_value"

    assert verify_ashby_signature(secret, body, wrong_signature) is False


def test_verify_ashby_signature_empty_signature():
    """Test that empty signatures fail verification."""
    secret = "test_secret"
    body = b'{"action": "test", "data": {}}'

    assert verify_ashby_signature(secret, body, "") is False


@flaky(max_runs=3, min_passes=1)
def test_verify_ashby_signature_timing_attack_resistance():
    """Test that signature comparison is resistant to timing attacks."""
    secret = "test_secret"
    body = b'{"action": "test", "data": {}}'

    # Generate correct signature
    hex_digest = hmac.new(secret.encode(), body, digestmod="sha256").hexdigest()
    correct_sig = f"sha256={hex_digest}"

    # Create signature that differs only in last char
    almost_correct_sig = correct_sig[:-1] + "0"

    # Measure time for correct vs incorrect (should be similar)
    iterations = 1000

    start = time.perf_counter()
    for _ in range(iterations):
        verify_ashby_signature(secret, body, correct_sig)
    correct_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        verify_ashby_signature(secret, body, almost_correct_sig)
    incorrect_time = time.perf_counter() - start

    # Time difference should be negligible (using constant-time compare)
    # Allow 10% variance for system noise
    assert abs(correct_time - incorrect_time) / correct_time < 0.1


def test_verify_ashby_signature_modified_body():
    """Test that signature fails when body is modified."""
    secret = "test_secret"
    original_body = b'{"action": "test", "data": {}}'
    hex_digest = hmac.new(
        secret.encode(), original_body, digestmod="sha256"
    ).hexdigest()
    signature = f"sha256={hex_digest}"

    modified_body = b'{"action": "test", "data": {"modified": true}}'

    assert verify_ashby_signature(secret, modified_body, signature) is False


def test_verify_ashby_signature_format():
    """Test that signature must include sha256= prefix."""
    secret = "test_secret"
    body = b'{"action": "test", "data": {}}'
    hex_digest = hmac.new(secret.encode(), body, digestmod="sha256").hexdigest()

    # Without prefix should fail
    assert verify_ashby_signature(secret, body, hex_digest) is False

    # With prefix should pass
    signature_with_prefix = f"sha256={hex_digest}"
    assert verify_ashby_signature(secret, body, signature_with_prefix) is True
