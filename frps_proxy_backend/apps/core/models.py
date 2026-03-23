from datetime import timezone
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class ProxyType(models.TextChoices):
    TCP = "tcp", "TCP"
    UDP = "udp", "UDP"
    HTTP = "http", "HTTP"

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
    expires_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def sync_status(self):
        if self.status != self.Status.ACTIVE:
            return
        if self.expires_at and self.expires_at < timezone.now():
            self.status = self.Status.INACTIVE
            self.save(update_fields=["status", "updated_at"])
        
    
class AccessToken(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="access_tokens")
    token_hash = models.CharField(max_length=255, unique=True)  # store hash of the token for security
    token_prefix = models.CharField(max_length=8, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    
    def sync_status(self):
        self.user.sync_status()
        
        changed = False
        if self.user.status != User.Status.ACTIVE and self.status != self.Status.INACTIVE:
            self.status = self.Status.INACTIVE
            changed = True
        if self.expires_at and self.expires_at <= timezone.now() and self.status != self.Status.INACTIVE:
            self.status = self.Status.INACTIVE
            changed = True
        if changed:
            self.save(update_fields=["status", "updated_at"])
            
    class TokenUtils:
        @classmethod
        def hash_token(cls, *, token):
            import hashlib
            return hashlib.sha256(token.encode()).hexdigest()

        @classmethod
        def prefix_token(cls, *, token):
            return token[:8]
        
        @classmethod
        def generate_access_token(cls, *, user: User, note: str = ""):
            def _generate_token():
                import secrets
                token = secrets.token_urlsafe(48)
                return token
            
            timeout = 20
            while timeout > 0:
                timeout -= 1
                token = _generate_token()
                token_hash = cls.hash_token(token=token)
                token_prefix = cls.prefix_token(token=token)
                
                if not AccessToken.objects.filter(token_hash=token_hash).exists():
                    access_token = AccessToken.objects.create(
                        user=user,
                        token_hash=token_hash,
                        token_prefix=token_prefix,
                        note=note
                    )
                    return token, access_token
            raise Exception("Failed to generate unique access token after multiple attempts")
        
        @classmethod
        def resolve_token(cls, *, token):
            access_tokens = AccessToken.objects.select_related("user").filter(
                token_hash=cls.hash_token(token=token),
                token_prefix=cls.prefix_token(token=token)
            )
            for access_token in access_tokens:
                access_token.sync_status()
                if access_token.status == AccessToken.Status.ACTIVE:
                    return access_token
            return None

    

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
    max_bandwidth_mbps = models.FloatField(default=5)
    max_average_bandwidth_mbps = models.FloatField(default=1)
    average_bandwidth_window_seconds = models.IntegerField(default=300)
    max_concurrent_conns = models.IntegerField(default=10)
    
    # others
    metadata = models.JSONField(default=dict, blank=True)  # for any extra info
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

class ProxyLease(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        SUSPENDED = "suspended", "Suspended"
        REJECTED = "rejected", "Rejected"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(AccessToken, on_delete=models.CASCADE, related_name="proxies")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="proxies")
    
    proxy_name = models.CharField(max_length=128)
    
    client_local_addr = models.CharField(max_length=255)
    client_local_port = models.IntegerField()
    client_public_addr = models.GenericIPAddressField(blank=True, null=True)
    
    server_addr = models.GenericIPAddressField(blank=True, null=True)
    server_port = models.IntegerField()
    proxy_type = models.CharField(max_length=20, choices=ProxyType.choices)  # e.g. "tcp", "udp", "http"
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    note = models.TextField(blank=True, null=True)
    
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    close_reason = models.CharField(max_length=255, blank=True, null=True)
