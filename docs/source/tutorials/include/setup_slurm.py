"""SSH plumbing for the SLURM container used by Module 4.

The docs build starts a ``xenonmiddleware/slurm:17`` Docker container that
exposes SSH on port 5001. This script:

1. Copies the pre-generated SSH key (shipped in ``.github/config/slurm_rsa``).
2. Writes an ``~/.ssh/config`` entry so that ``ssh slurm-ssh`` works.

The actual computer/code registration happens in live ``verdi`` cells inside
the tutorial notebook. This script only handles the SSH plumbing that would
be distracting to show in the tutorial.

If the SLURM container is not reachable (e.g. when running locally without
Docker), the script prints a warning and skips the setup.
"""

import pathlib
import shutil
import socket

SLURM_SSH_HOST = 'localhost'
SLURM_SSH_PORT = 5001
SLURM_SSH_USER = 'xenon'
COMPUTER_LABEL = 'slurm-ssh'

repo_root = pathlib.Path(__file__).resolve().parents[5]
slurm_key_src = repo_root / '.github' / 'config' / 'slurm_rsa'

ssh_dir = pathlib.Path.home() / '.ssh'
ssh_dir.mkdir(mode=0o700, exist_ok=True)
slurm_key_dst = ssh_dir / 'slurm_rsa'


def _container_reachable() -> bool:
    """Check whether the SLURM container's SSH port is open."""
    try:
        with socket.create_connection((SLURM_SSH_HOST, SLURM_SSH_PORT), timeout=2):
            return True
    except OSError:
        return False


if not _container_reachable():
    print(
        f'WARNING: SLURM container not reachable at {SLURM_SSH_HOST}:{SLURM_SSH_PORT}. '
        'Module 4 remote-execution cells will not work. '
        'Start the container with: docker run -d -p 5001:22 xenonmiddleware/slurm:17'
    )
else:
    # Key copy and ssh-config block are independent and each one self-heals.
    # A previous run may have written one but not the other (e.g. the key
    # source did not yet exist at the time, or `~/.ssh` was cleaned out
    # afterwards), so check and fix each on every run.

    if not slurm_key_src.exists():
        msg = f'expected SSH key for the SLURM container at {slurm_key_src}, but the file is missing'
        raise FileNotFoundError(msg)

    if not slurm_key_dst.exists() or slurm_key_dst.read_bytes() != slurm_key_src.read_bytes():
        shutil.copy(slurm_key_src, slurm_key_dst)
    slurm_key_dst.chmod(0o600)

    ssh_config = ssh_dir / 'config'
    marker = f'# --- AiiDA tutorial ({COMPUTER_LABEL}) ---'
    if not ssh_config.exists() or marker not in ssh_config.read_text():
        with open(ssh_config, 'a') as f:
            f.write(f'\n{marker}\n')
            f.write(f'Host {COMPUTER_LABEL}\n')
            f.write(f'    HostName {SLURM_SSH_HOST}\n')
            f.write(f'    User {SLURM_SSH_USER}\n')
            f.write(f'    Port {SLURM_SSH_PORT}\n')
            f.write(f'    IdentityFile {slurm_key_dst}\n')
            f.write('    StrictHostKeyChecking no\n')
            f.write('    UserKnownHostsFile /dev/null\n')
            f.write('    LogLevel ERROR\n')
