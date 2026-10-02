import sys, json
sys.path.insert(0, '.')
from desktop_agent.registry import PermissionManager, STATE

lock_exists = hasattr(PermissionManager, '_lock')

token = PermissionManager.mint_confirmation('test_tool', {'arg': 'val'})
ok1 = PermissionManager.validate_confirmation('test_tool', {'arg': 'val'}, token)
ok2 = PermissionManager.validate_confirmation('test_tool', {'arg': 'val'}, token)
single_use = ok1 and not ok2

token2 = PermissionManager.mint_confirmation('tool_a', {'x': 1})
wrong_tool = not PermissionManager.validate_confirmation('tool_b', {'x': 1}, token2)

token3 = PermissionManager.mint_confirmation('tool_c', {'x': 1})
wrong_args = not PermissionManager.validate_confirmation('tool_c', {'x': 2}, token3)

print(json.dumps({'lock': lock_exists, 'single_use': single_use, 'wrong_tool': wrong_tool, 'wrong_args': wrong_args}))
