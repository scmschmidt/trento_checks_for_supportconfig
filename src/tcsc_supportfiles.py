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
                
                # Detect virtualization.
                virt_block = SupportFiles._get_virtblock(basic_environment)
                try:
                    # AWS:      Manufacturer:  Amazon EC2
                    if virt_block['Manufacturer'] == 'Amazon EC2':
                        host_provider = 'aws'
                    
                    # Azure:    Manufacturer:  Microsoft Corporation
                    #           Hardware:      Virtual Machine    
                    elif virt_block['Manufacturer'] == 'Microsoft Corporation' and virt_block['Hardware'] == 'Virtual Machine':
                        host_provider = 'azure'
                    
                    # Google:   Manufacturer:  Google
                    #           Hardware:      Google Compute Engine
                    elif virt_block['Manufacturer'] == 'Google' and virt_block['Hardware'] == 'Google Compute Engine':
                        host_provider = 'azure' 
                        
                    # VMware:   Manufacturer:  VMware, Inc.
                    #           Hardware:      VMware.*
                    #           Hypervisor:    VMware (hardware platform)
                    #           Identity:      Virtual Machine (hardware platform)
                    elif virt_block['Manufacturer'] == 'VMware, Inc.' and virt_block['Hardware'].startswith('VMware') and virt_block['Hypervisor'] == 'VMware (hardware platform)' and virt_block['Identity'] == 'Virtual Machine (hardware platform)':
                        host_provider = 'azure'
                
                    # KVM:      Manufacturer:  QEMU
                    #           Hardware:      .*
                    #           Hypervisor:    KVM 
                    elif virt_block['Manufacturer'] == 'QEMU' and virt_block['Hypervisor'] == 'KVM':
                        host_provider = 'azure'
                                                                
                    # Nutanix:  (unknown)

                    # Default.                                                  
                    else:
                        host_provider = 'default'
                except:
                    host_provider = 'unknown'    
                    
                # TODO: Add auto detection.
                cluster_type = None
                architecture_type = None
                ensa_version = None
                filesystem_type = None
                hana_scenario = None    # NEW
                
                if hostname in self.result:
                    raise SupportFileException(f'{hostname} already present. Is "{file}" used twice?')
                
                if not provider:
                    provider = host_provider
                if provider != host_provider:
                    raise SupportFileException(f'Mixing providers is not allowed. Previous supportconfigs have "{provider}", but "{file} has "{host_provider}".')
                
                self.result[hostname] = {'provider': host_provider,
                                         'cluster_type': cluster_type,
                                         'architecture_type': architecture_type,
                                         'ensa_version': ensa_version,
                                         'filesystem_type': filesystem_type,
                                         'hana_scenario': hana_scenario,
                                         'supportconfig': file
                                        }    
            except Exception as err:
                        self.issues.append(err)
                        
    @staticmethod                        
    def _get_virtblock(basic_env_txt: str) -> Dict[str, str]:
        """Extracts virtualization information from basic-environment.txt
        provided as list of lines and returns them as dictionary."""
        
        try:
            virtulization = {}
            toggle = False
            for line in basic_env_txt:
                if toggle and line.startswith('#==['):
                    break
                if not toggle and line.startswith('# Virtualization'):
                    toggle = True
                    continue
                if toggle and ':' in line:
                    k, v = line.split(':')
                    virtulization[k.strip()] = v.strip()
        except:
            return {}
        return virtulization


class SupportFileException(Exception):
    pass       