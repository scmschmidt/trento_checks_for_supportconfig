#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the support files.
"""

import os
import tarfile
from typing import List, Dict, Tuple


class SupportFiles():
    """Represents supportfiles 
    """
    
    def __init__(self, supportfiles: List[str]) -> None:
        
        self.result = {}
        self.issues = []
        
        for file in [os.path.realpath(os.path.expandvars(os.path.expanduser(p))) for p in supportfiles]:
            try:
                sc = tarfile.open(file)
                basic_env = [f for f in sc.getnames() if f.endswith('/basic-environment.txt')]
                if basic_env:
                    with sc.extractfile(basic_env[0]) as f:
                        line = '#'
                        while line and line != b'# /bin/uname -a\n':
                            line = f.readline()                            
                        hostname = str(f.readline()).split(' ')[1]
                        while line and line != b'# Virtualization\n':
                            line = f.readline()  
                        virtualization = f.readline().decode().split(':')[1].strip()
                        if virtualization.startswith('Amazon EC2'):
                            provider = 'aws'
                        elif virtualization.startswith('Microsoft Corporation'):
                            provider = 'azure'
                        else:
                            provider = 'default'
                        
                        self.result[hostname] = {'provider': provider,
                                            'supportconfig': file
                                           }    
            except Exception as err:
                self.issues.append(err)

