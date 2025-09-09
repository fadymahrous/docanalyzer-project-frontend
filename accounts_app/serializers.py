# serializers.py
from rest_framework import serializers
from .models import User  # keep it relative
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        # include only fields you want to accept on create
        fields = [
            "username", "email", "password",
            "first_name", "last_name",
            "birthdate", "nationalid", "phonenumber"
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)  # hashes the password
        user.save()
        return user

    def update(self, instance, validated_data):
        # If password is provided, hash and update it
        password = validated_data.pop("password", None)
        if password:
            instance.set_password(password)
        # Update other fields that were passed in validated_data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
        


from rest_framework import serializers

class LoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, min_length=8,required=True)
