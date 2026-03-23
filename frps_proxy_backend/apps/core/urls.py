from django.urls import path
from . import views

urlpatterns = [
    path("handler", views.plugin_handler, name="plugin_handler"),
]