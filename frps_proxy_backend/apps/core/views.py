import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from .models import User, AccessToken, ProxyLease


def _parse_body(request):
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return None

def handle_close_proxy(content: dict, context: dict):
    from .service.auth import handle_close_proxy
    print("Handling close proxy with content:", content, "and context:", context)
    resp = handle_close_proxy(content=content)
    return resp.to_dict()

def handle_new_proxy(content: dict, context: dict):
    from .service.auth import handle_new_proxy
    print("Handling new proxy with content:", content, "and context:", context)
    resp = handle_new_proxy(content=content)
    return resp.to_dict()

@csrf_exempt
def plugin_handler(request):
    if not request.method == "POST":
        return JsonResponse({"reject": True, "reject_reason": "Only POST method is allowed"}, status=405)
    
    op = request.GET.get("op")
    version = request.GET.get("version")
    reqid = request.GET.get("reqid")
    
    body = _parse_body(request)
    print(body)
    if body is None:
        return JsonResponse({"reject": True, "reject_reason": "Invalid JSON body"}, status=400)
    
    content = body.get("content", {})
    if not isinstance(content, dict):
        return JsonResponse({"reject": True, "reject_reason": "Content must be a JSON object"}, status=400)
    
    context = {
        "op": op,
        "version": version,
        "reqid": reqid,
        "remote_addr": request.META.get("REMOTE_ADDR"),
    }
    
    if op == "NewProxy":
        resp = handle_new_proxy(content, context)
    elif op == "CloseProxy":
        resp = handle_close_proxy(content, context)
    else:
        return JsonResponse({"reject": True, "reject_reason": f"Unknown operation: {op}"}, status=400)
    print("Response:", resp)
    return JsonResponse(resp)
    
    
@csrf_exempt
def generate_token(request):
    from .service.auth import handle_create_token
    if not request.method == "GET":
        return JsonResponse({"error": "Only GET method is allowed"}, status=405)
    email = request.GET.get("email")
    resp = handle_create_token(email=email)
    
    return JsonResponse(resp, status=200 if "token" in resp else 400)

    