from scripts.kitty_builder import _extract_all_tool_calls
import json

test_str = """
<invoke name="generate_project_brief"></invoke>

<invoke name="read_file">
  <parameter name="path">src/api/system_routes.py</parameter>
</invoke>
"""

calls = _extract_all_tool_calls(test_str)
print("EXTRACTED:")
print(json.dumps(calls, indent=2))
