"""Read named secrets from the environment or an existing env file without executing it."""
import os
from pathlib import Path
import re


def read_secrets(names, env_file=None):
    """Return {name: value} for exactly the requested names; nothing else in the file is read or kept."""
    found = {name: os.environ.get(name) for name in names}
    missing = [name for name, value in found.items() if not value]
    if missing and env_file is not None:
        path = Path(env_file)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError('Use a regular, bounded env file')
        entries = {name: [] for name in missing}
        for line in path.read_text().splitlines():
            for name in missing:
                match = re.fullmatch(r'\s*(?:export\s+)?' + re.escape(name) + r'\s*=\s*(.*?)\s*', line)
                if match:
                    value = match[1]
                    if value[:1] in ('"', "'"):
                        if len(value) < 2 or value[-1] != value[0]:
                            raise ValueError('Invalid env entry')
                        value = value[1:-1]
                    entries[name].append(value)
        for name in missing:
            if len(entries[name]) != 1:
                raise ValueError(f'Expected exactly one {name} entry')
            found[name] = entries[name][0]
    for name, value in found.items():
        if not isinstance(value, str) or not re.fullmatch(r'[!-~]{1,512}', value):
            raise ValueError(f'A valid {name} is required')
    return found
