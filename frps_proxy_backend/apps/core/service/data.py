from dataclasses import dataclass

@dataclass
class FRPPluginResponse:
    reject: bool
    reject_reason: str = ""
    unchanged: bool = False
    content: dict = None
    
    def to_dict(self):
        if self.reject:
            return {"reject": True, "reject_reason": self.reject_reason}
        if self.unchanged:
            return {"reject": False, "unchange": True}
        return {"reject": False, "unchaged": False, "content": self.content or {}}
    