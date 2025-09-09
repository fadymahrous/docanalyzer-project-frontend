from django import forms
from django.forms import ModelForm
from django.contrib.auth.forms import UserCreationForm
from .models import User

class AuthenticationForm(forms.Form):
    username_or_email = forms.CharField(label="Email or Username", max_length=100)
    password = forms.CharField(label="Password", widget=forms.PasswordInput, max_length=100)

class CreateUser(UserCreationForm):
    birthdate = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),label="Birthdate"
    )
    class Meta:
        model = User
        fields = ["username", "password1", "password2", "birthdate", "email",'phonenumber']
