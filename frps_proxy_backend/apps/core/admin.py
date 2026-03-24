from django.contrib import admin
from .models import User, AccessToken, ProxyLease

# @admin.register(User)
# class UserAdmin(admin.ModelAdmin):
#     list_display = (
#         "email", "status", "expired_at",
#         "max_active_proxies", "max_bandwidth_mbps", "max_average_bandwidth_mbps", "average_bandwidth_window_seconds", "max_concurrent_conns"
#     )
#     list_filter = ("status",)
#     search_fields = ("email",)
    
@admin.register(ProxyLease)
class ProxyLeaseAdmin(admin.ModelAdmin):
    list_display = (
        "proxy_name", "proxy_type", 
        "remote_addr", "remote_port", 
        "status")
    list_filter = ("proxy_type", "status")
    search_fields = ("proxy_name", "remote_addr", "remote_port", "user__email")
