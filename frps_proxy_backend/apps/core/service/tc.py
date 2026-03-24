from ..models import User, ProxyLease, AccessToken, BandwidthPool
import copy
import os

TC_MANAGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../third_party/tc_manager/tc_manager.py")

def check_tc_manager_usable():
    if os.path.isfile(TC_MANAGER_PATH) and os.access(TC_MANAGER_PATH, os.X_OK):
        return
    raise RuntimeError(f"tc_manager cannot be executed or found at {TC_MANAGER_PATH}")
check_tc_manager_usable()

def _translate_frp_proxy_type_to_naive(proxy_type):
    if proxy_type in {"tcp", "http", "https"}:
        return "tcp"
    elif proxy_type in {"udp"}:
        return "udp"
    else:
        raise ValueError("Not supported proxy_type")        
    
def create_egress_tc_tree(*, total_garunteed_bandwidth_mbps=10, total_peak_bandwidth_mbps=None):
    if total_peak_bandwidth_mbps is None:
        total_peak_bandwidth_mbps = total_garunteed_bandwidth_mbps

    root_obj = {
        "name": "frp",
        "rate": f"{total_garunteed_bandwidth_mbps}mbit",
        "ceil": f"{total_peak_bandwidth_mbps}mbit",
        "children": []
    }
    
    pools = dict()
    users = dict()
    
    for pool in BandwidthPool.objects.all():
        pool_obj = {
            "name": f"{pool.name}",
            "rate": f"{pool.total_bandwidth_mbps}mbit",
            "ceil": f"{pool.total_bandwidth_mbps}mbit",
            "children": []
        }
        pools[pool.id] = pool_obj
        root_obj["children"].append(pool_obj)
    
    for user in User.objects.select_related("bandwidth_pool").filter(status=User.Status.ACTIVE):
        user_obj = {
            "name": f"{user.email}",
            "rate": f"{user.garunteed_bandwidth_mbps}mbit",
            "ceil": f"{user.peak_bandwidth_mbps}mbit",
            "selectors": []
        }

        users[user.id] = user_obj
        
        pool = user.bandwidth_pool
        pools[pool.id]["children"].append(user_obj)
        
    for lease in ProxyLease.objects.select_related("user").filter(status=ProxyLease.Status.ACTIVE):
        user = lease.user
        remote_port = lease.remote_port
        proxy_type = _translate_frp_proxy_type_to_naive(lease.proxy_type)
        selector = {"type": "ip", "sport": remote_port, "protocol": proxy_type}
        if not user.id in users:
            ## TODO: dangling proxy with no active user, should be cleanned
            # now just let it fail
            pass
        users[user.id]["selectors"].append(selector)

    return root_obj

def create_ingress_tc_tree(*, total_garunteed_bandwidth_mbps=10, total_peak_bandwidth_mbps=None):
    egress_tree = create_egress_tc_tree(
        total_garunteed_bandwidth_mbps=total_garunteed_bandwidth_mbps,
        total_peak_bandwidth_mbps=total_peak_bandwidth_mbps,
    )
    ingress_tree = copy.deepcopy(egress_tree)

    for pool in ingress_tree["children"]:
        for user in pool["children"]:
            for selector in user["selectors"]:
                selector["dport"] = selector.pop("sport")

    return ingress_tree


def create_tc_tree(*, total_garunteed_bandwidth_mbps, total_peak_bandwidth_mbps=None):
    tc_tree = {
        "version": 2,
        "dev": "br0",
        "egress": {
            "qdisc": {
                "kind": "htb",
                "handle": "1:",
                "default": "9999",
                "r2q": 10
            },
            "tree": {
                "name": "root",
                "id": "1:1",
                "rate": "1000mbit",
                "children": [
                    {
                        "name": "default",
                        "id": "1:9999",
                        "rate": "rest",
                        "selectors": [
                            { "type": "fwmark", "mark": 9999 }
                        ]
                    },
                    create_egress_tc_tree(total_garunteed_bandwidth_mbps=total_garunteed_bandwidth_mbps, total_peak_bandwidth_mbps=total_peak_bandwidth_mbps)
                ]
            }
        },
        "ingress": {
            "enable": True,
            "ifb": "ifb0",
            "qdisc": {
                "kind": "htb",
                "handle": "2:",
                "default": "9999",
                "r2q": 10
            },
            "tree": {
                "name": "root",
                "id": "2:1",
                "rate": "1000mbit",
                "children": [
                    {
                        "name": "default",
                        "id": "2:9999",
                        "rate": "rest"
                    },
                    create_ingress_tc_tree(total_garunteed_bandwidth_mbps=total_garunteed_bandwidth_mbps, total_peak_bandwidth_mbps=total_peak_bandwidth_mbps)
                ]
            }
        }
    }
    
    import tempfile, json
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        path = f.name
        json.dump(tc_tree, f)
    return path, tc_tree

def run_command(cmd):
    import subprocess
    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result

def check_tc_tree(*, tc_tree_path):
    # check if tree is legal
    ret = run_command([str(TC_MANAGER_PATH), "check", tc_tree_path])
    if ret.returncode != 0:
        raise RuntimeError("tc tree check fail: {tc_tree_path}, output={ret.stdout}")
    
    # check if tree compile
    ret = run_command([str(TC_MANAGER_PATH), "compile", tc_tree_path])
    if ret.returncode != 0:
        raise RuntimeError("tc tree compile fail: {tc_tree_path}, output={ret.stdout}")

def apply_tc_tree(*, tc_tree_path):
    check_tc_tree(tc_tree_path=tc_tree_path)
    
    ret = run_command([str(TC_MANAGER_PATH), "apply", tc_tree_path])
    if ret.returncode != 0:
        raise RuntimeError("tc tree apply fail: {tc_tree_path}, output={ret.stdout}")
    
def handle_create_tc(*, total_garunteed_bandwidth_mbps, total_peak_bandwidth_mbps):
    try:
        tc_tree_path, tc_tree = create_tc_tree(total_garunteed_bandwidth_mbps=total_garunteed_bandwidth_mbps, total_peak_bandwidth_mbps=total_peak_bandwidth_mbps)
        return {
            "tc_tree": tc_tree
        }
    except Exception as e:
        raise e
        return {
            "error": str(e)
        }

def handle_update_tc(*, total_garunteed_bandwidth_mbps, total_peak_bandwidth_mbps):
    try:
        tc_tree_path, tc_tree = create_tc_tree(total_garunteed_bandwidth_mbps=total_garunteed_bandwidth_mbps, total_peak_bandwidth_mbps=total_peak_bandwidth_mbps)
        apply_tc_tree(tc_tree_path=tc_tree_path)
        return {
            "tc_tree": tc_tree
        }
    except Exception as e:
        return {
            "error": str(e)
        }
        