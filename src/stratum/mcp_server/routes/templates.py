from typing import Any
from stratum.dao import template_dao
from oskill.render_template import render_template, TemplateVariableSpec

async def list_templates() -> list[dict[str, Any]]:
    templates = template_dao.list_templates()
    return [t.__dict__ for t in templates]

async def create_note_from_template(template_id: str, user_inputs: dict[str, Any]) -> str:
    template = template_dao.get_template(template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found")
    
    # In real impl, fetch variable specs from template frontmatter or DB
    variable_specs = [] 
    return render_template(template.content, variable_specs, user_inputs)
