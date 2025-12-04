"""
Utility modules for DinkyDash application.
"""
from dinkydash.utils.auth import hash_password, verify_password
from dinkydash.utils.rotation import get_current_person, get_person_for_date
from dinkydash.utils.countdown import calculate_days_remaining, get_target_date, format_countdown
from dinkydash.utils.images import save_image, delete_image, validate_image, get_image_url
from dinkydash.utils.tenant import (
    get_current_tenant_id,
    require_tenant,
    init_tenant_filter,
    register_tenant_models
)

__all__ = [
    # Auth utilities
    'hash_password',
    'verify_password',
    # Rotation utilities
    'get_current_person',
    'get_person_for_date',
    # Countdown utilities
    'calculate_days_remaining',
    'get_target_date',
    'format_countdown',
    # Image utilities
    'save_image',
    'delete_image',
    'validate_image',
    'get_image_url',
    # Tenant utilities
    'get_current_tenant_id',
    'require_tenant',
    'init_tenant_filter',
    'register_tenant_models',
]
