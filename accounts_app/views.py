from django.shortcuts import render, HttpResponse, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from helper.Get_Username_Object import UserFetcher
from .forms import CreateUser, AuthenticationForm
from helper.logger_setup import setup_logger
from django.contrib import messages
from .serializers import UserSerializer, LoginSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

logger = setup_logger('accounts_app')
get_user_parameters = UserFetcher()

# ---------- Helpers ----------

def ok(message: str, data: dict | None = None, http_status=status.HTTP_200_OK):
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    return Response(payload, status=http_status)

def fail(message: str, errors: dict | None = None, http_status=status.HTTP_400_BAD_REQUEST):
    payload = {"success": False, "message": message}
    if errors is not None:
        payload["errors"] = errors
    return Response(payload, status=http_status)

# ---------- HTML Views ----------

@ratelimit(key='ip', rate='10/m', block=True)  # a tad higher for HTML to reduce false blocks
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request.POST)
        if form.is_valid():
            username, password = get_user_parameters.get_user_from_form(form)
            if username is None:
                messages.error(request, "This user does not exist. Please register first.")
                return render(request, 'login.html', {'form': form})
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('home_app:home_page')            
            messages.error(request, "The password is not valid.")
            return render(request, 'login.html', {'form': form})
        messages.error(request, "Invalid form. Please contact the administrator.")
        return render(request, 'login.html', {'form': form})
    else:
        form = AuthenticationForm()
        if 'next' in request.GET:
            messages.warning(request, 'You must log in first to access this link.')
        return render(request, 'login.html', {'form': form})

@ratelimit(key='ip', rate='5/m', block=True)
def create_view(request):
    if request.method == "POST":
        form = CreateUser(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "User created successfully. You can now log in.")
            return redirect('accounts_app:login')
        else:
            messages.error(request,f'User creation failed {form.errors.as_json()}')
            return render(request, 'create_user.html', {'forms': form})
    form = CreateUser()
    return render(request, 'create_user.html', {'forms': form})

def logout_view(request):
    logout(request)
    messages.info(request, "User logged out successfully.")
    return redirect('home_app:home_page')

# ---------- API Views (DRF) ----------

# Properly apply ratelimit to class-based views via method_decorator
ratelimit_5pm = method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='dispatch')

@ratelimit_5pm
class UserCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if not serializer.is_valid():
            return fail("Invalid data.", errors=serializer.errors, http_status=status.HTTP_400_BAD_REQUEST)
        try:
            user = serializer.save()
            logger.info(f'User {user.username} created successfully')
            safe = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
            return ok("User created successfully.", data=safe, http_status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Failed to create user")
            return fail("Failed to create user.", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        serializer = UserSerializer()
        return ok(
            "This endpoint creates users (POST only).",
            data={"fields_required": list(serializer.fields.keys())},
            http_status=status.HTTP_200_OK
        )

@ratelimit_5pm
class UpdateUserAPI(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        # Support partial update with PUT for convenience
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return fail("Invalid data.", errors=serializer.errors, http_status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
            logger.info(f"User {request.user.username} updated successfully")
            return ok("User updated successfully.", http_status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error updating user {request.user.username}: {e}")
            return fail("Failed to update user.", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return fail("Invalid data.", errors=serializer.errors, http_status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
            logger.info(f"User {request.user.username} patched successfully")
            return ok("User updated successfully.", http_status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error patching user {request.user.username}: {e}")
            return fail("Failed to update user.", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@ratelimit_5pm
class DeleteUserAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        try:
            username = user.username
            user.delete()
            logger.info(f"User {username} deleted.")
            return ok("User deleted successfully.", http_status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error deleting user {getattr(user, 'id', 'unknown')}: {e}")
            return fail("Failed to delete user.", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@ratelimit_5pm
class RequestTokenAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return fail("Invalid inputs.", errors=serializer.errors, http_status=status.HTTP_400_BAD_REQUEST)

        # Avoid user enumeration: return 401 for any bad credentials path
        try:
            username, password = get_user_parameters.get_user_from_serializer(serializer)
            if not username or not password:
                return fail("Invalid username or password.", http_status=status.HTTP_401_UNAUTHORIZED)

            user = authenticate(request, username=username, password=password)
            if not user:
                return fail("Invalid username or password.", http_status=status.HTTP_401_UNAUTHORIZED)

            refresh_token = RefreshToken.for_user(user)
            access_token = refresh_token.access_token
            logger.info(f"Token issued for user {user.username}")
            return ok(
                "Token issued.",
                data={"refresh": str(refresh_token), "access": str(access_token)},
                http_status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Token issuance failed")
            return fail("Authentication service error.", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
