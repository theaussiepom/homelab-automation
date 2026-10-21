#!/usr/bin/env python3
"""Parse public configuration and render Compose with only synthetic inputs.

No HA instance, device, Docker daemon or private environment file is contacted.
"""
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[2]
TAGS = {'!secret', '!include', '!include_dir_list', '!include_dir_named',
        '!include_dir_merge_list', '!include_dir_merge_named', '!env_var', '!input', '!env'}
class PublicLoader(yaml.SafeLoader):
    pass

def tagged(loader, node):
    if node.tag not in TAGS or not isinstance(node, yaml.ScalarNode):
        raise ValueError('Unexpected YAML tag')
    value = loader.construct_scalar(node)
    if not value.strip():
        raise ValueError('Empty YAML reference')
    return value
for tag in TAGS:
    PublicLoader.add_constructor(tag, tagged)

def checked(argv, **kwargs):
    result = subprocess.run(argv, capture_output=True, timeout=30, **kwargs)
    if result.returncode:
        raise ValueError('Syntax or model validation failed')
    return result.stdout

def compose_variables(value, required=False, reject_empty=False):
    """Inspect YAML values, consuming escaped dollar pairs before variables."""
    result = set()
    if isinstance(value, dict):
        children = value.values()
    elif isinstance(value, list):
        children = value
    elif isinstance(value, str):
        for match in re.finditer(r'\$\$|\$\{([_a-zA-Z][_a-zA-Z0-9]*)(:?\?)?|\$([_a-zA-Z][_a-zA-Z0-9]*)', value):
            name = match[1] or match[3]
            if name and (not required or match[2]) and (not reject_empty or match[2] == ':?'):
                result.add(name)
        return result
    else:
        return result
    for child in children:
        result.update(compose_variables(child, required, reject_empty))
    return result

def interpolation_expressions(text):
    """Yield complete expressions; escaped dollars never open an expression."""
    offset = 0
    pattern = re.compile(r'\$\$|\$\{([_a-zA-Z][_a-zA-Z0-9]*)(:?[-+?])?|\$([_a-zA-Z][_a-zA-Z0-9]*)')
    while match := pattern.search(text, offset):
        offset = match.end()
        if not match[1]:
            continue
        depth, end = 1, offset
        while end < len(text) and depth:
            if text[end] == '{':
                depth += 1
            elif text[end] == '}':
                depth -= 1
            end += 1
        if depth:
            raise ValueError('Unclosed Compose interpolation')
        yield match[1], match[2], text[offset:end-1], text[match.start():end]
        offset = end

def compose_required_probes(value):
    """Select an active branch for each requirement, including repeated names.

    A probe uses the original expression in a synthetic scalar field so an
    independent field cannot mask its error when a guard variable is unset.
    Compose still validates the complete model before these focused probes.
    """
    probes = []
    states = {'unset', 'empty', 'nonempty'}
    branches = {'-': {'unset'}, ':-': {'unset', 'empty'},
                '+': {'empty', 'nonempty'}, ':+': {'nonempty'}}

    def constrain(guards, name, allowed):
        selected = guards.get(name, states) & allowed
        return {**guards, name: selected} if selected else None

    def visit(expression, guards, root, depth=0):
        if depth > 32:
            raise ValueError('Compose interpolation nesting limit exceeded')
        name, operator, operand, _ = expression
        if operator in ('?', ':?'):
            for state in (('unset', 'empty') if operator == ':?' else ('unset',)):
                selected = constrain(guards, name, {state})
                if selected is None:
                    continue  # No failing input can also activate this branch.
                values = {}
                for key, allowed in selected.items():
                    values[key] = ('fixture-only' if 'nonempty' in allowed else
                                   None if 'unset' in allowed else '')
                probes.append((root, name, values))
            # Error-message interpolation is not an input to successful startup.
        elif operator in branches:
            selected = constrain(guards, name, branches[operator])
            if selected is not None:
                for nested in interpolation_expressions(operand):
                    visit(nested, selected, root, depth+1)

    def values(item):
        if isinstance(item, dict):
            for child in item.values():
                values(child)
        elif isinstance(item, list):
            for child in item:
                values(child)
        elif isinstance(item, str):
            for expression in interpolation_expressions(item):
                visit(expression, {}, expression[3])

    values(value)
    return probes

def compose(path):
    text = path.read_text()
    model = yaml.safe_load(text)
    variables = compose_variables(model)
    with tempfile.TemporaryDirectory(prefix='compose-public-fixture-') as temp:
        scratch = Path(temp)
        dummy = scratch / 'synthetic.env'
        dummy.write_text('FIXTURE_ONLY=yes\n')
        env = {'PATH': os.environ['PATH'], 'HOME': str(scratch), 'COMPOSE_DISABLE_ENV_FILE': '1'}
        for variable in variables:
            if variable == 'TZ':
                value = 'UTC'
            elif variable in {'DOMAIN', 'DOMAIN_ALIAS'}:
                value = 'example.invalid'
            elif variable.endswith('_PREFIX'):
                value = '192.0.2'
            elif any(x in variable for x in ('IPV4_ADDRESS', '_DNS_', '_GATEWAY_')):
                value = '192.0.2.10'
            elif any(x in variable for x in ('_SUBNET_', '_IP_RANGE_')):
                value = '192.0.2.0/24'
            elif variable.endswith('_JSON') or 'ZBX_SSO_SETTINGS' in variable:
                value = '{}'
            elif variable.endswith('_FILE'):
                value = str(dummy)
            elif variable.endswith(('_ROOT', '_DIR')):
                value = str(scratch)
            else:
                value = 'fixture-only'
            env[variable] = value
        for service in model.get('services', {}).values():
            if 'env_file' in service:
                service['env_file'] = [str(dummy)]
        for section in ('secrets', 'configs'):
            for entry in model.get(section, {}).values():
                if isinstance(entry, dict) and 'file' in entry:
                    entry['file'] = str(dummy)
        argv = ['docker', 'compose', '--env-file', '/dev/null', '--project-directory',
                str(scratch), '--project-name', 'public-fixture', '-f', '-',
                'config', '--format', 'json']
        data = yaml.safe_dump(model, sort_keys=False).encode()
        output = checked(argv, input=data, env=env)
        parsed = json.loads(output)
        if not parsed.get('services'):
            raise ValueError('Empty Compose model')
        for expression, variable, overrides in compose_required_probes(model):
            missing = dict(env)
            for name, value in overrides.items():
                if value is None:
                    missing.pop(name, None)
                else:
                    missing[name] = value
            probe = {'services': {'app': {'image': 'example.invalid/fixture:1',
                                         'environment': {'VALUE': expression}}}}
            result = subprocess.run(argv, input=yaml.safe_dump(probe).encode(),
                                    env=missing, capture_output=True, timeout=30)
            expected = ('required variable ' + variable + ' is missing a value').encode()
            if result.returncode == 0 or expected not in result.stderr:
                raise ValueError('Required private input did not fail closed')
        return len(parsed['services'])

def run(root=ROOT):
    counts, failures = {}, []
    renderer = os.environ.get('TRAEFIK_FIXTURE_RENDERER')
    # Git's tracked file list defines source; no runtime or untracked files read.
    names = checked(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
    for name in filter(None, names):
        path = root / name
        try:
            kind = None
            if path.suffix in {'.yaml', '.yml'} or name.endswith(('.yaml.example', '.yml.example', '.yaml.in')):
                text = path.read_text()
                if name.startswith('traefik/conf.d/') and '{{' in text:
                    if not renderer:
                        raise ValueError('Traefik fixture renderer required')
                    text = checked([renderer, str(path)]).decode()
                list(yaml.load_all(text, Loader=PublicLoader))
                kind = 'yaml'
            elif path.suffix in {'.json', '.code-workspace'} or name.endswith('.json.example'):
                json.loads(path.read_text()); kind = 'json'
            elif path.suffix == '.py':
                ast.parse(path.read_text(), filename=name); kind = 'python'
            elif path.suffix == '.js':
                # Browser modules need module parsing; Node-RED uses CommonJS.
                argv = ['node', '--check']
                if '/www/' in name:
                    argv += ['--input-type=module']
                checked(argv, input=path.read_bytes()); kind = 'javascript'
            elif path.suffix == '.php':
                checked(['php', '-n', '-l', str(path)]); kind = 'php'
            elif path.suffix == '.sh' or name in {'.githooks/pre-commit', '.githooks/pre-push'}:
                checked(['bash', '-n', str(path)]); kind = 'shell'
            if kind:
                counts[kind] = counts.get(kind, 0) + 1
            if name.startswith('compose/') and path.name == 'compose.yaml':
                compose(path); counts['compose'] = counts.get('compose', 0) + 1
        except Exception as exc:
            failures.append({'path': name, 'error_type': type(exc).__name__})
    return {'status': 'failed' if failures else 'passed', 'checks': counts,
            'failures': failures, 'service_actions': 0, 'private_inputs_read': 0,
            'limitations': ['Syntax and synthetic Compose models only; not HA runtime acceptance',
                            'Includes, secrets and external deployment mounts are not resolved']}

if __name__ == '__main__':
    result = run()
    print(json.dumps(result))
    sys.exit(bool(result['failures']))
