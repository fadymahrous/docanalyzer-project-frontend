from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal

from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)

class User(AbstractUser):
    email = models.EmailField(unique=True)
    birthdate = models.DateField(null=True, blank=True)
    nationalid = models.CharField(max_length=50,blank=True, null=True)
    phonenumber = models.CharField(max_length=20, null=False)
    wallet = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    objects = UserManager()
    REQUIRED_FIELDS = ["email","birthdate", "phonenumber"]

    def __str__(self):
        return f"{self.username} - {self.email}"