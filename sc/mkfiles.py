#!/usr/bin/env python3

import grp
import os
import pwd
import sys

def perm2oct(permission: str) -> str:
    perms = ['---', '--x', '-w-', '-wx', 'r--', 'r-x', 'rw-', 'rwx']
    oct = []
    for c in range(0, 8, 3):
        oct.append(str(perms.index(permission[c:c+3])))
    return int(f'''0o{''.join(oct)}''', 8)

# Parsing file list.
files = []
base_dir = None
with open(sys.argv[1], 'r') as f:
    for line in f.readlines():
        line = line.strip()
        if line.startswith('/'):
            base_dir = line[:-2]
        elif line.startswith('total '):
            continue
        elif line.endswith(' ..'):
            continue
        elif line.endswith(' .'):
            details = line.split()
            files.append((details[0][0], details[0][1:], details[2], details[3], base_dir))
            continue
        else:
            try:
                details = line.split()
                files.append((details[0][0], details[0][1:], details[2], details[3], f'{base_dir}{details[8]}'))
            except:
                pass

# Creating files.
for file in files:
    t, perm, user, group, name = file
    try:
        perm_int = perm2oct(perm)
        if t == 'd':
            print(f'Creating directory "{name}" ({perm} {user}:{group})')
            os.makedirs(name, mode=perm_int, exist_ok=True)
        else:
            print(f'Creating file "{name}" ({perm} {user}:{group})')
            f = os.open(name, os.O_CREAT, mode=perm_int)
            os.close(f)
        os.chown(name, pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid)
    except Exception as err:
        print(f'Creating "{name}" failed: {err}')    
    
# Bye.
sys.exit(0)

