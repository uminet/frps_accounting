from django.utils import timezone
from ..models import AccessToken, User


def handle_login(data: dict):
    if not "content" in data:
        raise ValueError("Missing 'content' field in request data")
    content = data["content"]
    
    if not "user" in content:
        raise ValueError("Missing 'user' field in request content")
    
    token = content["user"]
    access_token = AccessToken.TokenUtils.resolve_token(token=token)
    if not access_token:
        raise ValueError("Invalid access token")
    
    
    
    