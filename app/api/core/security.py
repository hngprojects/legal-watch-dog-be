import json
from typing import Any, Dict

from app.api.core.config import get_cipher_suite


def encrypt_auth_details(data: Dict[str, Any]) -> str:
    """Converts JSON dict -> Encrypted String"""
    if not data:
        return None
    cipher_suite = get_cipher_suite()
    json_str = json.dumps(data)
    return cipher_suite.encrypt(json_str.encode()).decode()


def decrypt_auth_details(encrypted_data: str) -> Dict[str, Any]:
    """Converts Encrypted String -> JSON dict"""
    if not encrypted_data:
        return {}
    try:
        cipher_suite = get_cipher_suite()
        decrypted_json = cipher_suite.decrypt(encrypted_data.encode()).decode()
        return json.loads(decrypted_json)
    except Exception:
        return {}
