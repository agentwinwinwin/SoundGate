from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import DeviceViewSet, LoginView, LogoutView, MeView, RegisterView
router = DefaultRouter()
router.register('devices', DeviceViewSet, basename='device')
urlpatterns = [path('auth/register/', RegisterView.as_view()), path('auth/login/', LoginView.as_view()), path('auth/me/', MeView.as_view()), path('auth/logout/', LogoutView.as_view())] + router.urls
