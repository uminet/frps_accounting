from django.urls import path
from . import views

urlpatterns = [
    path("handler", views.plugin_handler, name="plugin_handler"),
    path("generate_token", views.generate_token, name="generate_token"),
]