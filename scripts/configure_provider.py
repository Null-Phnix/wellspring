"""Copy the owner-authorized DeepSeek key to the one Wellspring SSM parameter."""
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from aws_task import aws_env

def main():
    PARAMETER = '/wellspring/ask/provider_key'
    key = None
    for line in Path.home().joinpath('.hermes/.env').read_text().splitlines():
        name, separator, value = line.strip().removeprefix('export ').partition('=')
        if separator and name == 'DEEPSEEK_API_KEY':
            parts = shlex.split(value, comments=True)
            key = parts[0] if parts else None
            break
    if not key:
        raise SystemExit('The approved DeepSeek key is not configured.')
    # The secret travels through process memory, not argv, disk artifacts, or normal output.
    request = {'Name': PARAMETER, 'Value': key, 'Type': 'SecureString',
               'Overwrite': True, 'Tier': 'Standard',
               'Description': 'Wellspring Ask provider key; owner-managed source remains local.'}
    # This host's AWS wrapper consumes stdin. An inherited anonymous memory file
    # preserves the payload without a secret-bearing disk file or argument value.
    fd = os.memfd_create('wellspring-provider-payload', flags=0)
    try:
        os.write(fd, json.dumps(request).encode())
        os.lseek(fd, 0, os.SEEK_SET)
        result = subprocess.run(
            ['aws', 'ssm', 'put-parameter', '--region', 'ca-central-1',
             '--cli-input-json', f'file:///proc/self/fd/{fd}', '--output', 'json'],
            pass_fds=(fd,), capture_output=True, text=True, env=aws_env())
    finally:
        os.close(fd)
    if result.returncode:
        safe = result.stderr.replace(key, '[REDACTED]')
        safe = re.sub(r'(?:AKIA|ASIA)[A-Z0-9]{16}', '[REDACTED_ACCESS_KEY_ID]', safe)
        print(json.dumps({'status':'failed','safe_error':safe.strip()[:1500]}))
        raise SystemExit('SSM provider-key update failed.')
    metadata = json.loads(result.stdout)
    print(json.dumps({'parameter': PARAMETER, 'version': metadata['Version'],
                      'type': 'SecureString', 'value_printed': False}))


if __name__ == "__main__":
    main()
