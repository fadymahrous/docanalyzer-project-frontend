from django.urls import path,include
from . import views
from rest_framework.routers import DefaultRouter
from django.urls import path
from rest_framework_simplejwt.views import (TokenObtainPairView,TokenRefreshView,)

app_name = "accounts_app"

urlpatterns = [
    path('login/',views.login_view,name='login'),
    path('logout/',views.logout_view,name='logout'),
    path('create_view/',views.create_view,name='create_view'),
    path("api/createuser/", views.UserCreateView.as_view(), name="createuser"),
    path('api/deleteuser/', views.DeleteUserAPI.as_view(), name='deleteuser'),
    path('api/updateuser/', views.UpdateUserAPI.as_view(), name='updateuser'),
    path('api/requesttoken/', views.RequestTokenAPI.as_view(), name='requesttoken'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]



