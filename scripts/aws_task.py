"""Run AWS CLI with only the three owner-authorized AWS environment values."""
import os
import shlex
import subprocess
import sys
from pathlib import Path


def aws_env():
    env = os.environ.copy()
    allowed = {'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN'}
    for line in Path.home().joinpath('.config/anubis/env.conf').read_text().splitlines():
        line = line.strip()
        if line.startswith('export '):
            line = line[7:]
        name, sep, raw = line.partition('=')
        if sep and name in allowed:
            values = shlex.split(raw, comments=True)
            if values:
                env[name] = values[0]
    env.update(AWS_DEFAULT_REGION='ca-central-1', AWS_REGION='ca-central-1', AWS_PAGER='')
    return env


if __name__ == '__main__':
    raise SystemExit(subprocess.run(['aws', *sys.argv[1:]], env=aws_env()).returncode)
