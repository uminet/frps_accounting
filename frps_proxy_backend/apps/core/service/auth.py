from ..models import AccessToken, User, ProxyLease
from .data import FRPPluginResponse
import psutil
from django.utils import timezone


def authenticate_token(*, token: str) -> AccessToken:
    token_hash = AccessToken.hash_token(token)
    try:
        access_token = AccessToken.objects.select_related("user").get(token_hash=token_hash)
    except AccessToken.DoesNotExist:
        raise AccessToken.Exceptions.TokenNotFound(f"Access token {token} not found")
    
    user = access_token.user
    if user is None:
        raise User.Exceptions.UserNotFound(f"User for access token {token} not found")
    if not user.is_valid:
        raise User.Exceptions.UserInvalid(f"User for access token {token} is invalid: expired at {user.expired_at}, status {user.status}")
    
    if not access_token.is_valid:
        raise AccessToken.Exceptions.TokenInvalid(f"Access token {token} is invalid: expired at {access_token.expeired_at}, status {access_token.status}")

    return access_token


def get_user_leases(*, user: User, active_only: bool = True):
    if active_only:
        return ProxyLease.objects.filter(user=user, status=ProxyLease.Status.ACTIVE)
    return ProxyLease.objects.filter(user=user)

def is_quota_sufficient(*, user: User) -> bool:
    active_leases_count = get_user_leases(user=user, active_only=True).count()
    return active_leases_count < user.max_active_proxies

def is_protocol_permitted(*, user: User, content: dict) -> bool:
    proxy_type = content.get("proxy_type")
    if proxy_type not in user.allowed_proxy_types:
        return False
    return True

def is_port_used(*, port: int, protocol: str = "tcp") -> bool:
    for conn in psutil.net_connections(kind=protocol):
        if conn.laddr.port == port:
            return True
    return False

def is_port_free(*, user: User, content: dict) -> bool:
    remote_port = content.get("remote_port")
    
    # check if port allowed for this user:
    port_range_start = user.port_range_start
    port_range_end = user.port_range_end
    if not (port_range_start <= remote_port <= port_range_end):
        return False
    
    # check if port is already occupied:
    protocol = content.get("proxy_type")
    if protocol in ["tcp", "https", "http"]:
        if is_port_used(port=remote_port, protocol="tcp"):
            return False
    if protocol in ["udp"]:
        if is_port_used(port=remote_port, protocol="udp"):
            return False
    return True

def create_proxy_lease(*, token: AccessToken, content: dict) -> ProxyLease:
    lease = ProxyLease.objects.create(
        proxy_name=content.get("proxy_name"),
        token=token,
        user=token.user,
        proxy_type=content.get("proxy_type"),
        remote_addr="",
        remote_port=content.get("remote_port"),
        status=ProxyLease.Status.ACTIVE,
        connected_at=timezone.now(),
    )
    return lease

def is_proxy_name_exists(*, proxy_name: str) -> bool:
    return ProxyLease.objects.filter(proxy_name=proxy_name, status=ProxyLease.Status.ACTIVE).exists()


def handle_new_proxy(*, content: dict) -> FRPPluginResponse:
    token = content.get("user", {}).get("user", "")
    try:
        access_token = authenticate_token(token=token)
    except (AccessToken.Exceptions.TokenNotFound, AccessToken.Exceptions.TokenInvalid, User.Exceptions.UserNotFound, User.Exceptions.UserInvalid) as e:
        return FRPPluginResponse(reject=True, reject_reason=str(e))
    
    user = access_token.user
    
    # hard error
    if not is_protocol_permitted(user=user, content=content):
        return FRPPluginResponse(reject=True, reject_reason=f"Proxy type {content.get('proxy_type')} is not allowed for this user")
    
    if not is_quota_sufficient(user=user):
        return FRPPluginResponse(reject=True, reject_reason=f"User has reached the maximum number of active proxies ({user.max_active_proxies})")
    
    # correctable error, now still reject
    if is_proxy_name_exists(proxy_name=content.get("proxy_name")):
        return FRPPluginResponse(reject=True, reject_reason=f"Proxy name {content.get('proxy_name')} is already in use")
    
    if not is_port_free(user=user, content=content):
        return FRPPluginResponse(reject=True, reject_reason=f"Port {content.get('remote_port')} is not allowed or already in use")
    
    # pass
    create_proxy_lease(token=access_token, content=content)
    return FRPPluginResponse(reject=False, unchanged=True)

def handle_close_proxy(*, content: dict) -> FRPPluginResponse:
    proxy_name = content.get("proxy_name")
    if not proxy_name:
        return FRPPluginResponse(reject=True, reject_reason="Missing 'proxy_name' in content")
    matched_leases = ProxyLease.objects.filter(proxy_name=proxy_name, status=ProxyLease.Status.ACTIVE)
    for lease in matched_leases:
        lease.status = ProxyLease.Status.CLOSED
        lease.closed_at = timezone.now()
        lease.close_reason = "Closed by user request"
        lease.save(update_fields=["status", "closed_at", "close_reason"])
    return FRPPluginResponse(reject=False, unchanged=True)

def handle_create_token(*, email: str) -> dict:
    if not email:
        return {"success": False, "reason": "Missing 'email' parameter"}
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return {"success": False, "reason": f"User with email {email} not found"}
    
    if not user.is_valid:
        return {"success": False, "reason": f"User with email {email} is invalid: expired at {user.expired_at}, status {user.status}"}
    
    token = AccessToken.create_token(user=user)
    return {"success": True, "token": token}
