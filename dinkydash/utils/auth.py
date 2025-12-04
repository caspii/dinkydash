"""
Authentication utilities.
Provides password hashing and verification functions.
"""
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password):
    """
    Hash a password using Werkzeug's secure password hashing.

    Args:
        password (str): Plain text password

    Returns:
        str: Hashed password suitable for database storage
    """
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password_hash, password):
    """
    Verify a password against its hash.

    Args:
        password_hash (str): Stored password hash from database
        password (str): Plain text password to verify

    Returns:
        bool: True if password matches hash, False otherwise
    """
    return check_password_hash(password_hash, password)
