import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render


def _parse_body(request):
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return None
    
def handle_login(content: dict, context: dict):
    print("Handling login with content:", content, "and context:", context)
    return {"reject": False, "unchange": True}

def handle_new_proxy(content: dict, context: dict):
    print("Handling new proxy with content:", content, "and context:", context)
    return {"reject": True, "reject_reason": "NewProxy operation is not supported yet"}

def handle_close_proxy(content: dict, context: dict):
    print("Handling close proxy with content:", content, "and context:", context)
    return {"reject": False, "unchange": True}

def handle_ping(content: dict, context: dict):
    print("Handling ping with content:", content, "and context:", context)
    return {"reject": False, "unchange": True}

def handle_new_work_conn(content: dict, context: dict):
    print("Handling new work conn with content:", content, "and context:", context)
    return {"reject": False, "unchange": True}

def handle_new_user_conn(content: dict, context: dict):
    print("Handling new user conn with content:", content, "and context:", context)
    return {"reject": False, "unchange": True}


@csrf_exempt
def plugin_handler(request):
    if not request.method == "POST":
        return JsonResponse({"reject": True, "reject_reason": "Only POST method is allowed"}, status=405)
    
    op = request.GET.get("op")
    version = request.GET.get("version")
    reqid = request.GET.get("reqid")
    
    body = _parse_body(request)
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
    
    if op == "Login":
        resp = handle_login(content, context)
    elif op == "NewProxy":
        resp = handle_new_proxy(content, context)
    elif op == "CloseProxy":
        resp = handle_close_proxy(content, context)
    elif op == "Ping":
        resp = handle_ping(content, context)
    elif op == "NewWorkConn":
        resp = handle_new_work_conn(content, context)
    elif op == "NewUserConn":
        resp = handle_new_user_conn(content, context)
    else:
        return JsonResponse({"reject": True, "reject_reason": f"Unknown operation: {op}"}, status=400)
    
    return JsonResponse(resp)
    
    