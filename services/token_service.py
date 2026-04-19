"""
Token service – create, validate, and revoke HMAC-signed UUID tokens.
"""
import uuid
import hmac
import hashlib
from flask import current_app
from extensions import db
from models import Token


def _compute_hmac(token_value: str) -> str:
    """Compute HMAC-SHA256 signature for a token string."""
    secret = current_app.config["HMAC_SECRET"].encode("utf-8")
    return hmac.new(secret, token_value.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_token(user_id: int) -> Token:
    """
    Create a new UUID token for a user, compute its HMAC signature,
    and persist to the database.  Any existing token for the user is
    revoked first.
    """
    # Look for any existing token (revoked or not) to strictly respect unique=True
    token = Token.query.filter_by(user_id=user_id).first()

    token_value = uuid.uuid4().hex  # 32-char hex string
    signature = _compute_hmac(token_value)

    if token:
        token.token = token_value
        token.hmac_signature = signature
        token.is_revoked = False
    else:
        token = Token(
            user_id=user_id,
            token=token_value,
            hmac_signature=signature,
        )
        db.session.add(token)

    db.session.commit()
    return token


def validate_token(token_value: str, signature: str):
    """
    Validate a token + HMAC pair.
    Returns (Token, error_string | None).
    """
    if not token_value or not signature:
        return None, "missing"

    # Recompute HMAC and compare (constant-time)
    expected_sig = _compute_hmac(token_value)
    if not hmac.compare_digest(expected_sig, signature):
        return None, "tampered"

    token = Token.query.filter_by(token=token_value).first()
    if token is None:
        return None, "not_found"

    if token.is_revoked:
        return None, "revoked"

    return token, None


def revoke_token(user_id: int) -> bool:
    """Revoke all active tokens for a user."""
    tokens = Token.query.filter_by(user_id=user_id, is_revoked=False).all()
    for t in tokens:
        t.is_revoked = True
    db.session.commit()
    return len(tokens) > 0


def get_active_token(user_id: int):
    """Return the active (non-revoked) token for a user, or None."""
    return Token.query.filter_by(user_id=user_id, is_revoked=False).first()
