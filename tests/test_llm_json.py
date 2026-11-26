import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import pytest

from lib.llm_json import extract_json_object


class TestExtractJsonObject:
    def test_plain_json(self):
        assert extract_json_object('{"name": "A"}') == {"name": "A"}

    def test_code_fenced_json(self):
        assert extract_json_object('```json\n{"name": "A"}\n```') == {"name": "A"}

    def test_prose_around_json_without_fence(self):
        text = 'Here is the metadata:\n{"name": "A", "tags": ["gpu"]}\nHope that helps!'
        assert extract_json_object(text) == {"name": "A", "tags": ["gpu"]}

    def test_nested_object_and_braces_in_strings(self):
        text = 'x {"name": "A {b}", "meta": {"k": 1}} y'
        assert extract_json_object(text) == {"name": "A {b}", "meta": {"k": 1}}

    def test_skips_non_json_braces_before_real_object(self):
        assert extract_json_object('use {braces} then {"name": "A"}') == {"name": "A"}

    @pytest.mark.parametrize('text', ['', '   ', 'no json here', '[1, 2]'])
    def test_raises_when_no_object(self, text):
        with pytest.raises(ValueError):
            extract_json_object(text)
