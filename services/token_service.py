import uuid
import hmac
import hashlib
from flask import current_app
from extensions import db
from models import Token


def _compute_hmac(token_value: str) -> str:
    
    secret = current_app.config["HMAC_SECRET"].encode("utf-8")
    return hmac.new(secret, token_value.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_token(user_id: int) -> Token:
    

    token = Token.query.filter_by(user_id=user_id).first()

    token_value = uuid.uuid4().hex
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
    
    if not token_value or not signature:
        return None, "missing"


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
    
    tokens = Token.query.filter_by(user_id=user_id, is_revoked=False).all()
    for t in tokens:
        t.is_revoked = True
    db.session.commit()
    return len(tokens) > 0


def get_active_token(user_id: int):
    
    return Token.query.filter_by(user_id=user_id, is_revoked=False).first()
