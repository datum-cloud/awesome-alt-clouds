import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import parse_readme_to_json as parser

README = """# T

## Workload Clouds

* 🟢 [Alpha](https://alpha.io/) - Runs models. <!-- tags: llm-inference, gpu -->
* 🟡🔵 [Beta](https://beta.io/) - Early thing.

## Service Clouds

* 🟢 [Alpha](https://alpha.io/) - Runs models. <!-- tags: agent-native -->
* 🟢 [Gamma](https://gamma.io/) - Legacy bullet.
"""


def _parse(tmp_path):
    p = tmp_path / "README.md"
    p.write_text(README)
    return {c["name"]: c for c in parser.parse_readme(str(p))}


def test_tags_and_description_split(tmp_path):
    a = _parse(tmp_path)["Alpha"]
    assert a["description"] == "Runs models."
    assert a["tags"] == ["llm-inference", "gpu", "agent-native"]
    assert a["categories"] == ["Workload Clouds", "Service Clouds"]


def test_unverified_flag(tmp_path):
    b = _parse(tmp_path)["Beta"]
    assert b["unverified"] is True and b["score"] == 2


def test_legacy_bullet_has_no_new_keys(tmp_path):
    g = _parse(tmp_path)["Gamma"]
    assert "tags" not in g and "unverified" not in g and g["score"] == 3


def test_output_is_json_serializable(tmp_path):
    json.dumps(list(_parse(tmp_path).values()))
