"""Security utilities for webhook verification."""

import hashlib
import hmac

from structlog import get_logger

logger = get_logger()


def verify_ashby_signature(
    secret: str,
    body: bytes,
    provided_signature: str,
) -> bool:
    """
    Verify Ashby webhook signature using HMAC-SHA256.

    Uses constant-time comparison to prevent timing attacks.

    Ashby signature format: "sha256=<hex_digest>"

    Args:
        secret: Webhook secret from environment
        body: Raw request body
        provided_signature: Ashby-Signature header (format: "sha256=...")

    Returns:
        True if signature valid, False otherwise
    """
    # Compute expected signature
    h = hmac.new(secret.encode(), body, hashlib.sha256)
    expected_digest = h.hexdigest()
    expected_signature = f"sha256={expected_digest}"

    # Constant-time comparison (security critical!)
    is_valid = hmac.compare_digest(expected_signature, provided_signature)

    if not is_valid:
        logger.warning(
            "webhook_signature_invalid",
            expected_prefix=expected_signature[:15],
            provided_prefix=provided_signature[:15] if provided_signature else None,
        )

    return is_valid
