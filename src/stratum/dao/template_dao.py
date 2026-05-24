from typing import Any, Optional
from dataclasses import dataclass

@dataclass
class Template:
    id: str
    name: str
    content: str

def create_template(id: str, name: str, content: str) -> Template:
    return Template(id=id, name=name, content=content)

def get_template(template_id: str) -> Optional[Template]:
    return None

def list_templates() -> list[Template]:
    return []
