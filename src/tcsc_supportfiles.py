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
        
        provider = None
        for file in supportfiles:            
            
            # If HOST_ROOT_FS is set, we run inside a container and all paths
            # need to be prefixed with the content of that variable: the mount
            # point of the host's rootfs.
            # Also we have to prefix relative paths with the (imported) $PWD
            # to be correct first.
            if 'HOST_ROOT_FS' in os.environ:
                file = f'''{os.getenv('HOST_ROOT_FS')}{file}''' if file.startswith('/') else  f'''{os.getenv('HOST_ROOT_FS')}/{os.getenv('PWD')}/{file}'''   
            
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
                            host_provider = 'aws'
                        elif virtualization.startswith('Microsoft Corporation'):
                            host_provider = 'azure'
                        else:
                            host_provider = 'default'
                        
                        if hostname in self.result:
                            raise SupportFileException(f'{hostname} already present. Is "{file}" used twice?')
                        
                        if not provider:
                            provider = host_provider
                        if provider != host_provider:
                            raise SupportFileException(f'Mixing providers is not allowed. Previous supportconfigs have "{provider}", but "{file} has "{host_provider}".')
                        
                        self.result[hostname] = {'provider': host_provider,
                                            'supportconfig': file
                                           }    
            except Exception as err:
                self.issues.append(err)


class SupportFileException(Exception):
    pass       