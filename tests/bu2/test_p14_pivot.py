import json

from stratum.services.bu_v2_p14_loader import _collect_cjk, _replace


def test_cjk_strings_are_collected_and_replaced_without_touching_ids():
    dump = {"id": "synthesis_1", "concepts": [{"id": "c1", "label": "极限", "definition": "limit"}]}
    found: dict[str, None] = {}
    _collect_cjk(dump, found)
    assert list(found) == ["极限"]
    out = _replace(dump, {"极限": "limit"})
    assert out["concepts"][0] == {"id": "c1", "label": "limit", "definition": "limit"}
    assert json.dumps(out).count("synthesis_1") == 1
