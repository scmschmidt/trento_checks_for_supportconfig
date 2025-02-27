#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the support files.
"""

import os
import re
import sys
import tarfile
from typing import List, Dict, Tuple
#import xml.etree.ElementTree as ElementTree
import defusedxml.ElementTree as ElementTree

class SupportFiles():
    """Represents supportfiles 
    """
    
    def __init__(self, supportfiles: List[str]) -> None:
        
        self.result = {}
        self.issues = []
        
        provider = None
        overall_ensa_version = None
        type = 'host' if len(supportfiles) == 1 else 'cluster'
        
        for file in supportfiles:            
            
            # If HOST_ROOT_FS is set, we run inside a container and all paths
            # need to be prefixed with the content of that variable: the mount
            # point of the host's rootfs.
            # Also we have to prefix relative paths with the (imported) $PWD
            # to be correct first.
            if 'HOST_ROOT_FS' in os.environ:
                file = f'''{os.getenv('HOST_ROOT_FS')}{file}''' if file.startswith('/') else  f'''{os.getenv('HOST_ROOT_FS')}/{os.getenv('PWD')}/{file}'''   

            try:
                subfiles = {}
                subfilenames = ['basic-environment.txt', 'ha.txt', 'rpm.txt', 'plugin-ha_sap.txt']
                if os.path.isfile(file):
                    with tarfile.open(file) as sc:
                        for txt_file in subfilenames:
                            filenames = [f for f in sc.getnames() if f.endswith('/' + txt_file)]     
                            if not filenames:
                                raise SupportFileException(f'"{file}" does not contain a "{txt_file}"!')
                            subfiles[txt_file] = [str(line, sys.getdefaultencoding()) for line in sc.extractfile(filenames[0]).readlines()]    
                elif os.path.isdir(file):
                    try:
                        for txt_file in subfilenames:
                            with open(file + '/' + txt_file) as f:
                                subfiles[txt_file] = f.readlines()
                    except Exception as err:
                        raise SupportFileException(f'Error reading "{file}/{txt_file}": {err}')
                else:
                    raise SupportFileException(f'Unsupported file type for "{file}".')

                hostname = subfiles['basic-environment.txt'][subfiles['basic-environment.txt'].index('# /bin/uname -a\n') + 1].split(' ')[1]
                ra_packages = SupportFiles._get_packages(['SAPHanaSR', 'SAPHanaSR-ScaleOut'], subfiles['rpm.txt'])

                # Detect virtualization.
                virt_block = SupportFiles._get_virtblock(subfiles['basic-environment.txt'])
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
                    
                # Detect environment settings.
                cib = SupportFiles._get_cib(subfiles['ha.txt'])
                if type == 'cluster' and cib:
                    
                    # Detect cluster_type and architecture_type.
                    # architecture_type: one of classic, angi	(if cluster_type is one of hana_scale_up, hana_scale_out)
                    # cluster_type: one of hana_scale_up, hana_scale_out, ascs_ers (if target_type is cluster)
                    #
                    # If <cluster_property_set id="SAPHanaSR"> exists in the CIB, we have HANA cluster, 
                    # otherwise ascs_ers is assumed.
                    # To distinguish between ScaleUp and ScaleOut, in angi a nvpair with value "ScaleUp"
                    # or "ScaleOut" exists: <nvpair id="..." name="..." value="Scale..."/>
                    # In classic the installed RPM package can be used to distinguish between hana_scale_up and hana_scale_out:
                    # SAPHanaSR -> hana_scale_up, SAPHanaSR-ScaleOut -> hana_scale_out,
                    if cib.findall(".//cluster_property_set[@id='SAPHanaSR']"):
                        if 'SAPHanaSR-ScaleOut' in ra_packages:
                            cluster_type = 'hana_scale_out'
                            architecture_type = 'classic'
                        else: 
                            scale_up = cib.findall(".configuration/crm_config/cluster_property_set[@id='SAPHanaSR']/nvpair[@value='ScaleUp']")
                            scale_out =cib.findall(".configuration/crm_config/cluster_property_set[@id='SAPHanaSR']/nvpair[@value='ScaleOut']")
                            if scale_up:
                                cluster_type = 'hana_scale_up'
                                architecture_type = 'angi'
                            elif scale_out:
                                cluster_type = 'hana_scale_out'
                                architecture_type = 'angi'
                            else:
                                cluster_type = 'hana_scale_up'
                                architecture_type = 'classic'
                    else:
                        cluster_type = 'ascs_ers'
                        architecture_type = None
                                       
                    # Detect filesystem_type.
                    # one of resource_managed, simple_mount, mixed_fs_types	(if cluster_type is ascs_ers)
                    #
                    # If each SAP system (SID) contains the primitive type `Filesystem` we have `resource_managed`.
                    # If each SAP system (SID) does not contain the primitive type `Filesystem` we have `simple_mount`.
                    # Otherwise it is `mixed_fs_types`. In case of multiple SIDs, it is always `mixed_fs_types`.
                    #
                    # SID is not explicit part of the CIB. The presence in the group id is not guaranteed!
                    # Therefore we have a cheap implementation:
                    # If every group (instance) has a filesystem primitive, we have resource_managed.
                    # If no group (instance) has a filesystem primitive, we have simple_mount.
                    # Otherwise we have mixed_fs_types.
                    if cluster_type == 'ascs_ers':
                        groups = cib.findall(".//group")   # finding all groups
                        groups_with_filesystem_primitive = cib.findall(".//primitive[@type='Filesystem']...")   # parent of filesystem primitive
                        if len(groups_with_filesystem_primitive) == 0:
                            filesystem_type = 'simple_mount'
                        else:
                            filesystem_type = 'resource_managed' if len(groups) == len(groups_with_filesystem_primitive) else 'mixed_fs_types'
                    else:
                        filesystem_type = None 

                    # Detect hana_scenario. 
                    # one of performance_optimized, cost_optimized, unknown	(if cluster_type is hana_scale_up)
                    if cluster_type == 'hana_scale_up':
                        if cib.findall("./configuration/resources//primitive[@type='SAPInstance']"):
                            hana_scenario = 'cost_optimized'
                        else:
                            hana_scenario = 'performance_optimized'   
                    else:
                        hana_scenario = None

                    # Detect ensa_version.
                    # one of ensa1, ensa2, mixed_versions (if cluster_type is ascs_ers)
                    #
                    # The output of `sapcontrol -nr XX -function GetProcessList` for the ERS instance 
                    # (part of `plugin-ha_sap.txt`) contains in the process table
                    # '^enq_replicator, Enqueue Replicator 2,.*%' for ensa2 and 
                    # '^enrepserver, EnqueueReplicator,.*%' for ensa1.
                    #
                    # Only the supportconfig of the node where the ERS instance is running, contains
                    # the output. Therefore further down, ensa_version will be aligned about all hosts!
                    ensa_version = None
                    if cluster_type == 'ascs_ers':
                        for process_list in SupportFiles.get_instanceprocesses(subfiles['plugin-ha_sap.txt']):
                            for line in process_list:
                                if line.startswith('enrepserver, EnqueueReplicator,'):
                                    ensa_version = 'ensa1'
                                    break
                                if line.startswith('enq_replicator, Enqueue Replicator 2,'):
                                    ensa_version = 'ensa2'
                                    break
                            if ensa_version:
                                overall_ensa_version = ensa_version
                                break
                    
                else:
                    cluster_type = None
                    architecture_type = None
                    ensa_version = None
                    filesystem_type = None
                    hana_scenario = None


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
                        
        # Align ensa_version (see above in detection part, why).
        if overall_ensa_version:
            for data in self.result.values():
                if data['cluster_type'] == 'ascs_ers':
                    data['ensa_version'] = overall_ensa_version

                        
    @staticmethod                        
    def _get_virtblock(basic_env_txt: List[str]) -> Dict[str, str]:
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

    @staticmethod                        
    def _get_cib(ha_txt:  List[str]) -> ElementTree:
        """Extracts cib.xml from ha.txt provided as list of lines and 
        returns it as XML element tree."""
        
        try:
            cib = []
            toggle = False
            for line in ha_txt:
                if toggle and line.startswith('#==['):
                    break
                if not toggle and line.startswith('# /var/lib/pacemaker/cib/cib.xml'):
                    toggle = True
                    continue
                if toggle:
                    cib.append(line)
            return ElementTree.fromstring(''.join(cib))
        except:
            return None

    @staticmethod                        
    def _get_packages(packages: List[str], rpm_txt: List[str]) -> List[str]:
        """Searches for the given package names in rpm.txt provided as list of lines and 
        returns a list with the findings."""

        try:
            packages_list = []
            toggle = False
            for line in rpm_txt:
                if toggle and line.startswith('#==['):
                    break
                if not toggle and line.startswith('# rpm -qa --queryformat'):
                    toggle = True
                    continue
                if toggle:
                    try:
                        packages_list.append(line.split()[0])
                    except:
                        pass
            return [p for p in packages if p in packages_list[1:]]
        except:
            return []

    @staticmethod
    def get_instanceprocesses(plugin_sap_ha_txt: List[str]) -> List[List[str]]:
        """Extracts GetProcessList information from plugin-sap_ha.txt provided
        as list of lines and returns a list with the output lines (lines)."""

        try:
            start_getprocesslist = re.compile(r'^# /bin/su - \w+ -c \'sapcontrol -nr [0-9]+ -function GetProcessList\'')
            instances, instance = [], []
            toggle = False
            for line in plugin_sap_ha_txt:
                if toggle and line.startswith('#==['):
                    toggle = False
                    instances.append(instance)
                    instance = []
                    continue
                if not toggle and start_getprocesslist.match(line):
                    toggle = True
                    continue
                if toggle:
                    instance.append(line.strip())
            return instances
        except:
            return []


class SupportFileException(Exception):
    pass       