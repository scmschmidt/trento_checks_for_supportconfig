#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the support files.
"""

import os
import sys
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
                if os.path.isfile(file):
                    with tarfile.open(file) as sc:
                        basic_env = [f for f in sc.getnames() if f.endswith('/basic-environment.txt')]
                        if not basic_env:
                            raise SupportFileException(f'"{file}" does not contain a "basic-environment.txt".')
                        basic_environment = [str(line, sys.getdefaultencoding()) for line in sc.extractfile(basic_env[0]).readlines()]
                elif os.path.isdir(file):
                    with open(f'{file}/basic-environment.txt') as f:
                        basic_environment = f.readlines()
                else:
                    raise SupportFileException(f'Unsupported file type for "{file}".')

                hostname = basic_environment[basic_environment.index('# /bin/uname -a\n') + 1].split(' ')[1]
                virtualization = basic_environment[basic_environment.index('# Virtualization\n') + 1].split(':')[1].strip()

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