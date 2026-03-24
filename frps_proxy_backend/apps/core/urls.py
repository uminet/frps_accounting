from django.urls import path
from . import views

urlpatterns = [
    path("handler", views.plugin_handler, name="plugin_handler"),
    path("generate_token", views.generate_token, name="generate_token"),
    path("update_tc", views.update_tc, name="update_tc"),
    path("create_tc", views.create_tc, name="create_tc")
]