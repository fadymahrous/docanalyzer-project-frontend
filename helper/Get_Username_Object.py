from typing import Optional, Tuple
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from accounts_app.models import User
from helper.logger_setup import setup_logger


logger=setup_logger('accounts_app')
email_validator = EmailValidator()

class UserFetcher:
    def get_user_by_email(self, email: str) -> Optional[User]:
        try:
            email_validator(email)
        except ValidationError:
            logger.error(f"The Provided email is not valid email format, Email Passed:{email}")
            return None
        try:
            return User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            logger.error(f"Multiple users found for email, Email Passed:{email}, | (Should be Unique)")
            return None

    def get_user_from_form(self, form) -> Tuple[Optional[str], Optional[str]]:
        """Return (username, password) if the form is valid & user exists, else (None, None).
        Note: Do not verify password here—use authenticate().
        """
        username_or_email = form.cleaned_data.get("username_or_email")
        password = form.cleaned_data.get("password")

        if not username_or_email or not password:
            return None, None

        # Resolve user by email or username (case-insensitive)
        user = None
        try:
            try:
                email_validator(username_or_email)
                user = User.objects.get(email__iexact=username_or_email)
            except ValidationError:
                user = User.objects.get(username__iexact=username_or_email)
        except User.DoesNotExist:
            # Generic log to avoid leaking which identifier failed
            logger.info(f"The user passed not exist, User passed {username_or_email}")
            return None, None
        except User.MultipleObjectsReturned:
            logger.warning("The user passed returned multiple objects, User passed {username_or_email} | (Should be Unique)")
            return None, None

        # Don’t return the raw password; use authenticate where you handle login
        return (user.username, password)


    def get_user_from_serializer(self, serializer) -> Tuple[Optional[str], Optional[str]]:
        """Return (username, password) if the form is valid & user exists, else (None, None).
        Note: Do not verify password here—use authenticate().
        """
        username_or_email = serializer.validated_data.get("username_or_email")
        password = serializer.validated_data.get("password")

        if not username_or_email or not password:
            return None, None

        # Resolve user by email or username (case-insensitive)
        user = None
        try:
            try:
                email_validator(username_or_email)
                user = User.objects.get(email__iexact=username_or_email)
            except ValidationError:
                user = User.objects.get(username__iexact=username_or_email)
        except User.DoesNotExist:
            # Generic log to avoid leaking which identifier failed
            logger.info(f"The user passed not exist, User passed {username_or_email}")
            return None, None
        except User.MultipleObjectsReturned:
            logger.warning("The user passed returned multiple objects, User passed {username_or_email} | (Should be Unique)")
            return None, None

        # Don’t return the raw password; use authenticate where you handle login
        return (user.username, password)