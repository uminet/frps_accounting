from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid


class ProxyType(models.TextChoices):
    TCP = "tcp", "TCP"
    UDP = "udp", "UDP"
    STCP = "stcp", "STCP"
    SUDP = "sudp", "SUDP"
    HTTP = "http", "HTTP"
    HTTPS = "https", "HTTPS"
    
class BandwidthPool(models.Model):
    class Exceptions:
        class PeakCannotSatisfy(Exception):
            pass
        class TotalGarunteeCannotSatisfy(Exception):
            pass
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField(max_length=64, unique=True)
    total_bandwidth_mbps = models.FloatField(validators=[MinValueValidator(0)])
    
    @classmethod
    def get_default_pool(cls):
        pool, _ = cls.objects.get_or_create(
            name="default",
            defaults={"total_bandwidth_mbps": 10}
        )
        return pool.id
    
    def check_enough_bandwidth(self):
        users_in_pool = User.objects.filter(bandwidth_pool=self)
        total_user_garunteed_bandwidth_mbps = 0
        for user in users_in_pool:
            if user.peak_bandwidth_mbps > self.total_bandwidth_mbps:
                raise BandwidthPool.Exceptions.PeakCannotSatisfy(f"Peak cannot be satisfied for user {user.id} from pool {self.id}")
            total_user_garunteed_bandwidth_mbps += user.garunteed_bandwidth_mbps
        if total_user_garunteed_bandwidth_mbps > self.total_bandwidth_mbps:
            raise BandwidthPool.Exceptions.TotalGarunteeCannotSatisfy(
                f"Total bandwidth cannot be satisfied for pool {self.id}, "
                f"request: {total_user_garunteed_bandwidth_mbps}, have: {self.total_bandwidth_mbps}"
            )
            
class User(models.Model):
    class Exceptions:
        class UserNotFound(Exception):
            pass
        class UserInvalid(Exception):
            pass
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"
        PENDING = "pending", "Pending"
        
    # data
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INACTIVE)
    note = models.TextField(blank=True, null=True)
    expired_at = models.DateTimeField(blank=True, null=True)
    
    # permission
    def _default_allowed_proxies():
        return ["tcp"]
    port_range_start = models.PositiveIntegerField(default=20000, validators=[MinValueValidator(1), MaxValueValidator(65535)])
    port_range_end = models.PositiveIntegerField(default=30000, validators=[MinValueValidator(1), MaxValueValidator(65535)])
    allowed_proxy_types = models.JSONField(default=_default_allowed_proxies)
    
    max_active_proxies = models.PositiveIntegerField(default=1)
    garunteed_bandwidth_mbps = models.FloatField(default=0.5, validators=[MinValueValidator(0.0)])
    peak_bandwidth_mbps = models.FloatField(default=2, validators=[MinValueValidator(0.0)])
    max_concurrent_conns = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)])
    bandwidth_pool = models.ForeignKey(BandwidthPool, default=BandwidthPool.get_default_pool, on_delete=models.CASCADE)

    # metadata
    metadata = models.JSONField(default=dict, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def is_valid(self) -> bool:
        from django.utils import timezone
        if self.status != self.Status.ACTIVE:
            return False
        if self.expired_at and self.expired_at < timezone.now():
            return False
        return True
    
    def check_expiration(self):
        if not self.status == self.Status.ACTIVE:
            return
        if self.expired_at and self.expired_at < timezone.now():
            self.status = self.Status.INACTIVE
            self.save(update_fields=["status", "updated_at"])
    
class AccessToken(models.Model):
    class Exceptions:
        class TokenNotFound(Exception):
            pass
        class TokenInvalid(Exception):
            pass
        
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="access_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    token_prefix = models.CharField(max_length=8)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INACTIVE)
    expired_at = models.DateTimeField(blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @classmethod
    def hash_token(cls, token: str) -> str:
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def prefix_token(cls, token: str) -> str:
        return token[:8]
    
    @classmethod
    def generate_token(cls) -> str:
        import secrets
        return secrets.token_urlsafe(32)
    
    @classmethod
    def create_token(cls, user: User) -> str:
        while True:
            token = cls.generate_token()
            token_hash = cls.hash_token(token)
            token_prefix = cls.prefix_token(token)
            if not cls.objects.filter(token_hash=token_hash).exists():
                break
        cls.objects.create(user=user, token_hash=token_hash, token_prefix=token_prefix, status=cls.Status.ACTIVE)
        return token
        
    
    @property
    def is_valid(self) -> bool:
        from django.utils import timezone
        if self.status != self.Status.ACTIVE:
            return False
        if self.expired_at and self.expired_at < timezone.now():
            return False
        if not self.user.is_valid:
            return False
        return True
    
    def check_expiration(self):
        if not self.status == self.Status.ACTIVE:
            return
        if self.expired_at and self.expired_at < timezone.now():
            self.status = self.Status.INACTIVE
            self.save(update_fields=["status", "updated_at"])
            
class ProxyLease(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_id = models.CharField(max_length=64)
    proxy_name = models.CharField(max_length=255)
    token = models.ForeignKey(AccessToken, on_delete=models.CASCADE, related_name="proxy_leases")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="proxy_leases")
    proxy_type = models.CharField(max_length=20, choices=ProxyType.choices)
    remote_addr = models.GenericIPAddressField(null=True, blank=True)
    remote_port = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(65535)])
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    connected_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    close_reason = models.TextField(blank=True, null=True)

