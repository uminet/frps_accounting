import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"
        PENDING = "pending", "Pending"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    plan = models.ForeignKey("Plan", on_delete=models.PROTECT, related_name="users")
    note = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    
    # permissions
    allowed_proxy_types = models.JSONField(default=list)  # e.g. ["tcp", "udp"]    
    allow_http = models.BooleanField(default=False)
    
    # resources
    max_active_proxies = models.IntegerField(default=1)
    
    port_range_start = models.IntegerField(default=20000)
    port_range_end = models.IntegerField(default=30000)
    
    max_ports = models.IntegerField(default=1)
    max_bandwidth_mbps = models.FloatField(default=1)
    max_average_bandwidth_mbps = models.FloatField(default=1)
    average_bandwidth_window_seconds = models.IntegerField(default=300)
    max_concurrent_conns = models.IntegerField(default=10)
    
    # others
    metadata = models.JSONField(default=dict, blank=True)  # for any extra info
    
    created_at = models.DateTimeField(auto_now_add=True)
    
class Client(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"
        REVOKED = "revoked", "Revoked"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=100)
    
    token_hash = models.CharField(max_length=256)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    
    last_seen_at = models.DateTimeField(blank=True, null=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)  # for any extra info
    policy_override = models.JSONField(default=dict, blank=True)  # for any policy overrides
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ("user", "name")
        
class ProxyLease(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        REJECTED = "rejected", "Rejected"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="proxies")
    
    proxy_name = models.CharField(max_length=100)
    proxy_type = models.CharField(max_length=20)  # e.g. "tcp
    
    remote_port = models.IntegerField(null=True, blank=True)
    
    subdomain = models.CharField(max_length=100, null=True, blank=True)  # for http proxies
    custom_domains = models.JSONField(default=list, blank=True)  # for http proxies
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REJECTED)
    
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    
    close_reason = models.CharField(max_length=255, blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)  # for any extra info
    
    class Meta:
        index = [
            models.Index(fields=["client", "status"]),
            models.Index(fields=["remote_port"]),
        ]
        
class AuditLog(models.Model):
    class EventType(models.TextChoices):
        LOGIN = "login"
        LOGIN_FAIL = "login_fail"
        NEW_PROXY = "new_proxy"
        CLOSE_PROXY = "close_proxy"
        REJECT_PROXY = "reject_proxy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True)

    event_type = models.CharField(max_length=32, choices=EventType.choices)

    result = models.CharField(max_length=16)

    source_ip = models.GenericIPAddressField(null=True, blank=True)

    payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_type"]),
            models.Index(fields=["created_at"]),
        ]
    