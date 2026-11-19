"""Subscription-only Codex exec. Do not forward credentials on its command line."""
import json


def command(executable, model, servers, env, prompt):
    # CLI arms need localhost, the keychain (Aside) and LaunchServices (EgoLite), which every Codex seatbelt mode
    # blocks. Like the Claude harness, they run unsandboxed and are limited to ./browser by instruction only.
    argv = [executable, 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral',
            '--skip-git-repo-check', '--sandbox', 'read-only' if servers else 'danger-full-access', '--json', '--model', model]
    options = {'approval_policy': 'never', 'forced_login_method': 'chatgpt', 'web_search': 'disabled',
               'suppress_unstable_features_warning': True,
               'project_doc_max_bytes': 0, 'features.skip_host_skill_discovery': True,
               'skills.include_instructions': False, 'features.shell_tool': not servers}
    for feature in ('apps', 'browser_use', 'browser_use_external', 'in_app_browser', 'multi_agent', 'multi_agent_v2', 'plugins', 'hooks'):
        options['features.' + feature] = False
    if servers:
        server = servers['browser']
        server_env = server.get('env', {})
        env.update(server_env)
        options.update({'mcp_servers.browser.command': server['command'],
                        'mcp_servers.browser.args': server.get('args', []),
                        'mcp_servers.browser.required': True,
                        'mcp_servers.browser.default_tools_approval_mode': 'approve',
                        'mcp_servers.browser.env_vars': list(server_env)})
    for key, value in options.items():
        argv.extend(['-c', key + '=' + json.dumps(value)])
    return [*argv, '--', prompt]
