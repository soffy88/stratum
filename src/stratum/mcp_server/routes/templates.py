from typing import Any

# 3O 平台包仅部署于容器 /opt/platform；缺失时工具返回清晰错误而非 ImportError。
try:
    from oskill.render_template import render_template, TemplateVariableSpec

    _HAS_OSKILL_RENDER = True
except ImportError:  # pragma: no cover
    _HAS_OSKILL_RENDER = False
    render_template = None
    TemplateVariableSpec = None


def _get_dao():
    """Lazy DAO：dao 包不导出 template_dao 单例，按真实 API（TemplateDAO(db)）实例化。"""
    from stratum.dao.template import TemplateDAO
    from stratum.db import get_conn

    return TemplateDAO(get_conn())


async def list_templates() -> list[dict[str, Any]]:
    dao = _get_dao()
    return [t.__dict__ for t in dao.list_templates()]

async def create_note_from_template(template_id: str, user_inputs: dict[str, Any]) -> str:
    dao = _get_dao()
    template = dao.get_template(template_id=template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found")
    if not _HAS_OSKILL_RENDER:
        raise ValueError(
            f"Template rendering unavailable: 3O platform not deployed (no /opt/platform)"
        )
    
    # In real impl, fetch variable specs from template frontmatter or DB
    variable_specs = [] 
    return render_template(template.content, variable_specs, user_inputs)
