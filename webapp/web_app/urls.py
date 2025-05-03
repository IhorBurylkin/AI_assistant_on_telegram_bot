from django.urls import path
from . import views

urlpatterns = [
    path('check_form/api', views.check_form),
    path('check_form/api/submit', views.api_submit),
]