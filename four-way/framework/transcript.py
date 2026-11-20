"""Normalize Claude stream-json and Codex --json event logs into one attempt summary."""
from collections import Counter
import json


def _text(value, limit=300):
    if isinstance(value, list):
        value = ' '.join(v.get('text', '') if isinstance(v, dict) else str(v) for v in value)
    return str(value or '')[:limit]


def final_answer(text):
    """Text after the last 'FINAL ANSWER:' marker, else None (fixture tasks never ask for one)."""
    text = str(text or '')
    at = text.rfind('FINAL ANSWER:')
    return text[at + len('FINAL ANSWER:'):].strip().strip('`*').strip() if at >= 0 else None


def _events(stdout):
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def claude(stdout):
    tools, errors, final, result = Counter(), [], '', None
    names = {}
    for e in _events(stdout):
        message = e.get('message')  # some events (e.g. system notices) carry a plain string here
        content = (message.get('content') if isinstance(message, dict) else None) or []
        if e.get('type') == 'assistant':
            for block in content:
                if block.get('type') == 'tool_use':
                    names[block.get('id')] = block.get('name')
                    tools[block.get('name')] += 1
                elif block.get('type') == 'text':
                    final = block.get('text', '')
        elif e.get('type') == 'user':
            for block in content if isinstance(content, list) else []:
                if block.get('type') == 'tool_result' and block.get('is_error'):
                    errors.append({'tool': names.get(block.get('tool_use_id')), 'message': _text(block.get('content'))})
        elif e.get('type') == 'result':
            result = e
    usage = (result or {}).get('usage') or {}
    cached = usage.get('cache_read_input_tokens', 0)
    tokens = {'input': usage.get('input_tokens', 0) + usage.get('cache_creation_input_tokens', 0) + cached,
              'cached_input': cached, 'output': usage.get('output_tokens', 0)} if usage else None
    return {'completed': bool(result) and not result.get('is_error') and result.get('subtype') == 'success',
            'turns': (result or {}).get('num_turns'), 'cost_usd': (result or {}).get('total_cost_usd'),
            'tokens': tokens, 'tool_calls': sum(tools.values()), 'tools': dict(tools), 'tool_errors': errors,
            'final_message': _text((result or {}).get('result') or final, 600),
            'final_answer': final_answer((result or {}).get('result') or final)}


def codex(stdout):
    tools, errors, warnings, final, tokens, turns, failed = Counter(), [], [], '', None, 0, False
    for e in _events(stdout):
        kind = e.get('type')
        item = e.get('item') or {}
        if kind == 'item.completed':
            if item.get('type') == 'mcp_tool_call':
                name = item.get('tool')
                tools[name] += 1
                if item.get('status') == 'failed' or item.get('error'):
                    errors.append({'tool': name, 'message': _text((item.get('error') or {}).get('message') or item.get('result'))})
            elif item.get('type') == 'command_execution':
                tools['shell'] += 1
                if item.get('exit_code') not in (0, None) or item.get('status') == 'failed':
                    errors.append({'tool': 'shell', 'message': _text(item.get('aggregated_output'))})
            elif item.get('type') == 'agent_message':
                final = item.get('text', '')
            elif item.get('type') == 'error':
                errors.append({'tool': None, 'message': _text(item.get('message'))})
        elif kind == 'turn.completed':
            turns += 1
            u = e.get('usage') or {}
            tokens = tokens or {'input': 0, 'cached_input': 0, 'output': 0}
            tokens['input'] += u.get('input_tokens', 0)
            tokens['cached_input'] += u.get('cached_input_tokens', 0)
            tokens['output'] += u.get('output_tokens', 0)
        elif kind == 'turn.failed':
            failed = True
            warnings.append(_text((e.get('error') or {}).get('message')))
        elif kind == 'error':  # Non-fatal stream notices (config warnings, retries); fatal ones end in turn.failed.
            warnings.append(_text(e.get('message')))
    return {'completed': turns > 0 and not failed, 'turns': turns or None, 'cost_usd': None, 'tokens': tokens,
            'tool_calls': sum(tools.values()), 'tools': dict(tools), 'tool_errors': errors,
            'harness_warnings': warnings, 'final_message': _text(final, 600), 'final_answer': final_answer(final)}


def summarize(harness, stdout):
    return (codex if harness == 'codex' else claude)(stdout or '')
