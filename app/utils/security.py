
import hashlib
import hmac
import secrets


# ==========================================
# SECURE TOKEN GENERATION
# ==========================================

def generate_secure_token(
    length: int = 32,
) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Number of random bytes.

    Returns:
        URL-safe random token string.
    """

    if (
        isinstance(length, bool)
        or not isinstance(length, int)
        or length < 16
        or length > 128
    ):
        raise ValueError(
            "Token length must be between 16 and 128 bytes."
        )

    return secrets.token_urlsafe(length)


# ==========================================
# TOKEN HASHING
# ==========================================

def hash_token(
    token: str,
) -> str:
    """
    Create a SHA-256 hash of a token.

    Store the hash instead of storing the original
    sensitive token in the database.
    """

    if not isinstance(token, str) or not token:
        raise ValueError("A valid token is required.")

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# ==========================================
# TOKEN VERIFICATION
# ==========================================

def verify_token_hash(
    token: str,
    stored_hash: str,
) -> bool:
    """
    Verify a token against its stored SHA-256 hash.

    Uses constant-time comparison.
    """

    if (
        not isinstance(token, str)
        or not token
        or not isinstance(stored_hash, str)
        or not stored_hash
    ):
        return False

    calculated_hash = hash_token(token)

    return hmac.compare_digest(
        calculated_hash,
        stored_hash,
    )


# ==========================================
# CONSTANT-TIME VALUE COMPARISON
# ==========================================

def secure_compare(
    first_value: str,
    second_value: str,
) -> bool:
    """
    Compare two sensitive string values safely.
    """

    if (
        not isinstance(first_value, str)
        or not isinstance(second_value, str)
    ):
        return False

    return hmac.compare_digest(
        first_value.encode("utf-8"),
        second_value.encode("utf-8"),
    )
