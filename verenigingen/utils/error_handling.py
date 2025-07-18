"""
Standardized error handling utilities for Verenigingen app

This module provides consistent error handling patterns, logging utilities,
and custom exception types for the Verenigingen association management system.
"""

import time
import traceback
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

import frappe
from frappe import _


class VerenigingenException(frappe.ValidationError):
    """Base exception class for Verenigingen-specific errors"""

    pass


class MembershipError(VerenigingenException):
    """Raised when membership-related operations fail"""

    pass


class PaymentError(VerenigingenException):
    """Raised when payment processing fails"""

    pass


class SEPAError(PaymentError):
    """Raised when SEPA direct debit operations fail"""

    pass


class VolunteerError(VerenigingenException):
    """Raised when volunteer-related operations fail"""

    pass


class ChapterError(VerenigingenException):
    """Raised when chapter-related operations fail"""

    pass


class PermissionError(VerenigingenException):
    """Raised when user lacks required permissions"""

    pass


class ValidationError(VerenigingenException):
    """Raised when data validation fails"""

    pass


class ConfigurationError(VerenigingenException):
    """Raised when system configuration is invalid"""

    pass


def get_logger(module_name: str):
    """
    Get a standardized logger for a module

    Args:
        module_name: Name of the module (e.g., 'verenigingen.api.member_management')

    Returns:
        Configured logger instance
    """
    return frappe.logger(module_name, allow_site=True, file_count=50)


def log_error(error: Exception, context: Dict[str, Any] = None, module: str = None):
    """
    Log an error with standardized formatting and context

    Args:
        error: The exception that occurred
        context: Additional context information
        module: Module name where error occurred
    """
    logger = get_logger(module or "verenigingen.error")

    error_context = {
        "user": frappe.session.user if frappe.session else "System",
        "site": frappe.local.site if frappe.local else "Unknown",
        "error_type": type(error).__name__,
        "error_message": str(error),
        **(context or {}),
    }

    # Log the error with full context
    logger.error(f"Error in {module}: {str(error)}", extra=error_context, exc_info=True)

    # Also create a Frappe Error Log entry for tracking
    frappe.log_error(
        title=f"{module}: {type(error).__name__}", message=f"Error: {str(error)}\nContext: {error_context}"
    )


def handle_api_error(func: Callable) -> Callable:
    """
    Decorator to provide standardized error handling for API endpoints

    Usage:
        @frappe.whitelist()
        @handle_api_error
        def my_api_function():
            # Function implementation
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except VerenigingenException as e:
            # Known application errors - return structured error
            log_error(e, context={"function": func.__name__}, module=func.__module__)
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "code": getattr(e, "error_code", "VALIDATION_ERROR"),
                },
            }
        except frappe.PermissionError as e:
            # Permission errors
            log_error(e, context={"function": func.__name__}, module=func.__module__)
            return {
                "success": False,
                "error": {
                    "type": "PermissionError",
                    "message": _("Access denied: {0}").format(str(e)),
                    "code": "PERMISSION_DENIED",
                },
            }
        except frappe.ValidationError as e:
            # Frappe validation errors
            log_error(e, context={"function": func.__name__}, module=func.__module__)
            return {
                "success": False,
                "error": {"type": "ValidationError", "message": str(e), "code": "VALIDATION_ERROR"},
            }
        except Exception as e:
            # Unexpected errors - log with full traceback
            log_error(
                e,
                context={
                    "function": func.__name__,
                    "args": str(args)[:200],  # Limit arg length
                    "kwargs": str(kwargs)[:200],
                    "traceback": traceback.format_exc(),
                },
                module=func.__module__,
            )

            return {
                "success": False,
                "error": {
                    "type": "SystemError",
                    "message": _("An unexpected error occurred. Please contact support."),
                    "code": "SYSTEM_ERROR",
                },
            }

    return wrapper


def validate_required_fields(data: Dict[str, Any], required_fields: list) -> None:
    """
    Validate that required fields are present in data

    Args:
        data: Dictionary to validate
        required_fields: List of required field names

    Raises:
        ValidationError: If any required fields are missing
    """
    missing_fields = [field for field in required_fields if not data.get(field)]

    if missing_fields:
        raise ValidationError(_("Required fields missing: {0}").format(", ".join(missing_fields)))


def validate_email(email: str) -> None:
    """
    Validate email format

    Args:
        email: Email address to validate

    Raises:
        ValidationError: If email format is invalid
    """
    if not email or "@" not in email:
        raise ValidationError(_("Invalid email address: {0}").format(email))


def validate_postal_code(postal_code: str, country: str = "NL") -> None:
    """
    Validate postal code format for specific countries

    Args:
        postal_code: Postal code to validate
        country: Country code (default: NL for Netherlands)

    Raises:
        ValidationError: If postal code format is invalid
    """
    if country == "NL":
        # Dutch postal code format: 1234AB
        import re

        if not re.match(r"^\d{4}[A-Z]{2}$", postal_code.upper().replace(" ", "")):
            raise ValidationError(_("Invalid Dutch postal code format. Expected format: 1234AB"))
    # Add other country validations as needed


def require_permission(permission_type: str, throw: bool = True) -> bool:
    """
    Check if current user has required permission

    Args:
        permission_type: Type of permission to check
        throw: Whether to throw exception if permission denied

    Returns:
        True if user has permission

    Raises:
        PermissionError: If user lacks permission and throw=True
    """
    # Implementation depends on specific permission system
    # This is a placeholder for the actual permission checking logic

    has_perm = True  # Replace with actual permission check

    if not has_perm and throw:
        raise PermissionError(_("Access denied. Required permission: {0}").format(permission_type))

    return has_perm


def safe_get_doc(doctype: str, name: str, for_update: bool = False) -> Optional[Any]:
    """
    Safely get a document with proper error handling

    Args:
        doctype: Document type
        name: Document name
        for_update: Whether document will be updated

    Returns:
        Document instance or None if not found

    Raises:
        PermissionError: If user lacks read permission
    """
    try:
        return frappe.get_doc(doctype, name, for_update=for_update)
    except frappe.DoesNotExistError:
        return None
    except frappe.PermissionError as e:
        raise PermissionError(_("Access denied to {0} {1}").format(doctype, name)) from e


def safe_db_get_value(
    doctype: str, filters: Union[str, Dict], fieldname: Union[str, list], default: Any = None
) -> Any:
    """
    Safely get database value with error handling

    Args:
        doctype: Document type
        filters: Filters for the query
        fieldname: Field name(s) to retrieve
        default: Default value if not found

    Returns:
        Field value(s) or default
    """
    try:
        result = frappe.db.get_value(doctype, filters, fieldname)
        return result if result is not None else default
    except Exception as e:
        log_error(
            e,
            context={"doctype": doctype, "filters": str(filters), "fieldname": fieldname},
            module="verenigingen.utils.error_handling",
        )
        return default


def batch_process_with_error_handling(
    items: list, process_function: Callable, batch_size: int = 100
) -> Dict[str, Any]:
    """
    Process items in batches with comprehensive error handling

    Args:
        items: List of items to process
        process_function: Function to process each item
        batch_size: Number of items to process per batch

    Returns:
        Dictionary with success/error counts and failed items
    """
    results = {"total": len(items), "processed": 0, "errors": 0, "failed_items": []}

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]

        for item in batch:
            try:
                process_function(item)
                results["processed"] += 1
            except Exception as e:
                results["errors"] += 1
                results["failed_items"].append(
                    {"item": str(item), "error": str(e), "error_type": type(e).__name__}
                )

                log_error(
                    e,
                    context={
                        "item": str(item),
                        "batch_index": i // batch_size,
                        "item_index": results["processed"] + results["errors"],
                    },
                    module="verenigingen.utils.error_handling",
                )

        # Commit after each batch to avoid large transactions
        frappe.db.commit()

    return results


# Configuration for error handling
ERROR_HANDLING_CONFIG = {
    "max_error_message_length": 1000,
    "log_sensitive_data": False,
    "include_stack_trace": True,
    "error_notification_roles": ["System Manager", "Verenigingen System Admin"],
    "critical_error_threshold": 10,  # Number of errors before alerting
}


def cache_with_ttl(ttl=300):
    """
    Decorator to cache function results with time-to-live

    Args:
        ttl: Time to live in seconds (default: 5 minutes)

    Usage:
        @cache_with_ttl(ttl=600)
        def expensive_function():
            # Function implementation
    """

    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            current_time = time.time()

            # Check if we have a cached result that's still valid
            if cache_key in cache:
                cached_result, cached_time = cache[cache_key]
                if current_time - cached_time < ttl:
                    return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache[cache_key] = (result, current_time)

            # Clean up old cache entries (simple cleanup)
            keys_to_remove = []
            for key, (cached_result, cached_time) in cache.items():
                if current_time - cached_time >= ttl:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del cache[key]

            return result

        return wrapper

    return decorator


def setup_error_monitoring():
    """
    Set up error monitoring and alerting
    Called during app initialization
    """
    # This would set up error monitoring, alerting, etc.
    # Implementation depends on monitoring infrastructure
    pass
