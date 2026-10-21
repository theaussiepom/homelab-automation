#!/usr/bin/env python3
"""Run the existing GPT sensor request without shell interpretation."""

import base64
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

import yaml


EXPRESSIONS = (
    "{{ states('sensor.time') }}",
    "{{ now().strftime('%A') }}",
    "{{ states('weather.forecast_home') }}",
    "{{ states('sensor.outside_temperature') }}",
)


def build_argv(command, values):
    if not isinstance(values, list) or len(values) != len(EXPRESSIONS):
        raise ValueError("Expected four sensor values")
    if not all(isinstance(value, str) for value in values):
        raise ValueError("Sensor values must be strings")
    markers = [f"__GPT_SENSOR_VALUE_{i}__" for i in range(len(EXPRESSIONS))]
    for expression, marker in zip(EXPRESSIONS, markers, strict=True):
        if command.count(expression) != 1 or marker in command:
            raise ValueError("Unexpected request template")
        command = command.replace(expression, marker)
    argv = shlex.split(command)
    if len(argv) != 9 or argv[0] != "curl" or argv[1] != "-XPOST":
        raise ValueError("Unexpected request command")
    if argv[3] != "-H" or argv[5] != "-H" or argv[7] != "-d":
        raise ValueError("Unexpected request arguments")
    payload = json.loads(argv[8])
    replacements = dict(zip(markers, values, strict=True))
    pattern = re.compile('|'.join(map(re.escape, markers)))

    def substitute(value):
        if isinstance(value, str):
            return pattern.sub(lambda match: replacements[match.group()], value)
        if isinstance(value, list):
            return [substitute(item) for item in value]
        if isinstance(value, dict):
            return {key: substitute(item) for key, item in value.items()}
        return value

    argv[8] = json.dumps(substitute(payload), ensure_ascii=False)
    return argv


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError("Expected one encoded argument")
        values = json.loads(base64.b64decode(sys.argv[1], validate=True))
        secrets = yaml.safe_load(Path('/config/secrets.yaml').read_text())
        argv = build_argv(secrets['command_line_gpt_response'], values)
        result = subprocess.run(
            argv, shell=False, capture_output=True, timeout=14, check=False
        )
        if result.returncode:
            raise RuntimeError("Request failed")
        sys.stdout.buffer.write(result.stdout)
        return 0
    except Exception:
        # Never include request arguments or credentials in Home Assistant logs.
        print("GPT Response request failed", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
