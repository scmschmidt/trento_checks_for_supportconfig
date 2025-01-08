#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the Wanda container stack.
"""


import docker
import time
from rabbiteer import Rabbiteer, evaluate_check_results
from typing import List, Dict, Any, Tuple
from tcsc_config import *


class WandaStack():
    """Represents a Wanda container stack.
    
        - self._containers (Dict[str, Container]):  Dict with the Wanda container instances referenced by name.
        - self._docker (docker.DockerClient):  Instance of DockerClient.
        - self._rabbiteer (Rabbiteer):  Rabbiteer instance to talk to Wanda.
        - self.timeout (int):  Timeout for Docker and Wanda operations.
    """

    def __init__(self, config: Config) -> None:
        self._docker: docker.DockerClient = docker.from_env()
        self._dockerAPI: docker.APIClient = docker.APIClient()
        self.timeout: int = config.docker_timeout
        self._containers: Dict[str, docker.Container] = {container.name: container for container in 
                                                         self._docker.containers.list(
                                                             all=True, 
                                                             filters={'label': config.wanda_label})
                                                        }
        if set(self._containers.keys()) != set(config.wanda_containers):
            raise WandaException('Not all required Wanda containers are present.')
        self._rabbiteer = Rabbiteer(config.wanda_url)

    @property
    def container_status(self) -> Dict[str, Tuple[str, str]]:
        """Returns a dictionary with the name as key and a tuple with the current and expected
        status as value all Wanda containers, there current and expected status."""
        
        self._update()
        status = {}
        for container in self._containers.values():
            try:
                expected_status = container.labels['com.suse.tcsc.expected_state']
            except:
                raise WandaException(f'Could not get the label "com.suse.tcsc.expected_state" for {container.name}.')
            status[container.name] = (container.status, expected_status)
        return status
        
    @property
    def status(self) -> bool:
        """Returns a boolean with the Wanda status."""    
        
        for status in self.container_status.values():
            if status[0] != status[1]:
                return False

        try:
            health: str = self._rabbiteer.health()['database']
            ready: bool = self._rabbiteer.readiness()['ready']
        except:
            return False
        else:
            if ready and health == 'pass':
                return True 

        return False
    
    @property
    def mounts(self) -> Dict[str, List[str]]:
        """Returns dictionary with the name as key and the list of mounts as value
        for all Wanda containers."""
        
        self._update()
        return {container.name: self._dockerAPI.inspect_container(container.id)['Mounts'] for container in self._containers.values()}
        
    @property
    def mandatory_volume_present(self) -> Dict[str, Tuple[List[str], List[str]]]:
        """Returns a dictionary with the name of the container and a Tuple containing
        a list of the expected volumes and a list for the present volumes of all containers."""
        
        self._update()
        status = {}
        for container in self._containers.values():
            volumes = [mount['Name'] for mount in self._dockerAPI.inspect_container(container.id)['Mounts'] if mount['Type'] == 'volume']
            try:
                expected_volumes = container.labels['com.suse.tcsc.expected_volumes'].split(',')
            except:
                expected_volumes = None
            if not expected_volumes:
                continue
            status[container.name] = (expected_volumes, volumes)
        return status
        
    def checks(self, attributes: List[str] = None) -> List[dict]:
        """Returns list of Check instances for all available checks (content of 'items').
        The Check instance will have only the requested attributes.""" 

        return [Check(c, attributes) for c in self._rabbiteer.list_catalog().get('items')]   
       
    def check(self, check: str, attributes: List[str] = None) -> List[dict]:
        """Returns (first) Check instance for given check (content of 'items').
        The Check instance will have only the requested attributes.""" 
        try:
            return [Check(c, attributes) for c in self._rabbiteer.list_catalog().get('items') if check == c['id']][0]   
        except:
            return None
       
    def start(self) -> List[str]:
        """Initiate start of Wanda containers. Only containers, which are in the states
        'exited' or 'created' are going to be started. The method will *not* wait for 
        the containers to be up.
        Returns the names of the started containers."""
        
        started: List[str] = []
        self._update()
        for container in [c for c in self._containers.values() if c.status in ['exited', 'created']]:
            started.append(container.name)
            container.start()
            
        start_time = time.time()    
        while not self.status:
            if  (time.time() - start_time) > self.timeout: 
                raise WandaException(f'''Timeout of {self.timeout}s reached. Wanda did not became operational after start of containers: {', '.join(started)}''')
            time.sleep(1) 
        
        return started

    def stop(self) -> List[str]:
        """Stops all Wanda containers. Only containers, which are in the state 'running'
        are going to be stopped.
        Returns the names of the stopped containers."""

        stopped: List[str] = []
        self._update()
        
        for container in [c for c in self._containers.values() if c.status in ['running']]:
            stopped.append(container.name)
            container.stop(timeout=self.timeout)
               
        start_time: time.Time = time.time()
        while True:
            self._update()
            not_exited = [name for name, status in self.container_status.items() if status[0] != 'exited']
            if not not_exited:
                break
            if  (time.time() - start_time) > self.timeout: 
                raise WandaException(f'''Timeout of {self.timeout}s reached. Container not yet exited: {', '.join(not_exited)}''')
            time.sleep(1)   
        
        return stopped

    def execute_check(self, environment: Dict[str, str], agent_ids: List[str], check_id: str) -> Tuple[str, bool]:
        """Executes check on the given hosts and returns tuple with the result of `rabbiteer`
        as JSON string and False. In case of an error a tuple with the error string and True."""
        
        try:
            responses = self._rabbiteer.execute_checks(agent_ids, 
                                                      environment, 
                                                      [check_id], 
                                                      timeout=self.timeout, 
                                                      running_dots=False)
            result = evaluate_check_results(responses, brief=False, json_output=True)  
        except Exception as err:
            return err, True

        return result, False

    def _update(self) -> None:
        """Updates the container objects."""
        for container in self._containers.values():
            container.reload()

class WandaException(Exception):
    pass

class Check():
    """Represents a Trento check.
    The representation reads takes the original dictionary created from JSON
    and creates a reduced flat dictionary with only the parts required."""
 
    _known_gatherers = ['cibadmin', 'cibadmin@v1',
                        'corosync-cmapctl', 'corosync-cmapctl@v1',
                        'corosync.conf', 'corosync.conf@v1',
                        'hosts', 'hosts@v1',
                        'package_version', 'package_version@v1', 
                        'saphostctrl', 'saphostctrl@v1',
                        'sbd_config', 'sbd_config@v1',
                        'sbd_dump', 'sbd_dump@v1',
                        'systemd', 'systemd@v1', 'systemd@v2',
                        'verify_password', 'verify_password@v1',
                        'ascsers_cluster', 'ascsers_cluster@v1',
                        'sap_profiles', 'sap_profiles@v1',
                        'passwd', 'passwd@v1',
                        'groups', 'groups@v1',
                        'dir_scan', 'dir_scan@v1',
                        'sapservices', 'sapservices@v1',
                        'saptune', 'saptune@v1',
                        'sapcontrol', 'sapcontrol@v1',
                        'fstab', 'fstab@v1',
                        'disp+work', 'disp+work@v1',
                        'os-release', 'os-release@v1',
                        'mount_info', 'mount_info@v1',
                        'products', 'products@v1',
                        'sapinstance_hostname_resolver', 'sapinstance_hostname_resolver@v1',
                        'sysctl', 'sysctl@v1'
                       ]
    _valid_gatherers = ['cibadmin', 'cibadmin@v1',
                        'corosync.conf', 'corosync.conf@v1', 
                        'package_version', 'package_version@v1',
                        'sbd_config', 'sbd_config@v1',
                        'sbd_dump', 'sbd_dump@v1',
                        'sap_profiles', 'sap_profiles@v1',
                        'dir_scan', 'dir_scan@v1',
                        'sapservices', 'sapservices@v1',
                        'saptune', 'saptune@v1',
                        'fstab', 'fstab@v1',
                        'os-release', 'os-release@v1',
                        'sysctl', 'sysctl@v1'
                       ]
   
    _attribute_table = {'id': 'id', 
                        'description': 'description', 
                        'group': 'group', 
                        'metadata.provider': 'provider', 
                        'metadata.cluster_type': 'cluster_type', 
                        'metadata.architecture_type': 'architecture_type',
                        'metadata.ensa_version': 'ensa_version',
                        'metadata.filesystem_type': 'filesystem_type',
                        'metadata.hana_scenario': 'hana_scenario',
                        'facts[].gatherer': 'gatherer',
                        'expectations[].type': 'check_type',
                        'remediation': 'remediation'
                       }
    
    @staticmethod
    def gatherer2manifest(gatherer: str) -> List[str]:
        """Returns the list of manifest entries required for the given gatherer to work."""
        
        gatherer = gatherer.split('@')[0]
        map = {'cibadmin': ['pacemaker_files'],
               'corosync.conf': ['corosync.conf'],
               'hosts': ['hosts'],
               'package_version': ['rpm_packages'],
               'saphostctrl': ['saphostctrl'],
               'sbd_config': ['sysconfig_sbd'],
               'sbd_dump': ['sbd_dumps'],
               'sap_profiles': ['usr_sap'],
               'dir_scan': ['usr_sap', 'multi-user.target.wants'],
               'sapservices': ['sapservices'],
               'saptune': ['saptune'],
               'fstab': ['fstab'],
               'disp+work': ['disp+work'],
               'os-release': ['os-release'],
               'cibadmin': ['pacemaker_files'],
               'sysctl': ['sysctl']
              }
        return map[gatherer] if gatherer in map else None
    
    @staticmethod
    def _retrieve_attributes(dictionary: Dict, keys: List[str]):
        """Retrieves key-value pairs in a nested dictionary. The result is always a flat dictionary.
        Keys are written in dot-notation (e.g. 'metadata.cluster_type'). 
        Intermediate lists must be indicated by '[]' at the end of the key containing 
        the list (e.g. 'expectations[].type').
        If keys or indices are not found, None is returned."""
        
        def walk(subtree: Dict[str, Any], components: List[str]) -> Any:
            if components[0].endswith('[]'):
                real_key = components[0][:-2]
                elements = []
                for elem in subtree[real_key]:
                    elements.append(walk(elem, components[1:]))
                return elements    
            if len(components) > 1:
                return walk(subtree[components[0]], components[1:])
            return subtree[components[0]]

        data = {}
        for attribute in keys:
            components = attribute.split('.')
            try:
                value = walk(dictionary, components)
            except (KeyError, IndexError):
                value = None
            data[attribute] = value
        
        return data    
    
    def __init__(self, check: Dict, attributes: List[str] = None) -> None:

        if not attributes:
            attributes = Check._attribute_table.keys()

        if not set(attributes).issubset(Check._attribute_table.keys()):
            raise CheckException(f'Unsupported attributes: {set(attributes) - Check._attribute_table.keys()}')
        
        for key, value in Check._retrieve_attributes(check, attributes).items():
            for env in 'metadata.provider', 'metadata.cluster_type', 'metadata.architecture_type', 'metadata.ensa_version', 'metadata.filesystem_type', 'metadata.hana_scenario':
                if key == env and isinstance(value, str):
                    value = [value]
            if key == 'expectations[].type':
                if len(set(value)) != 1:
                    raise CheckException(f'''Unexpected expectation type for check {check['id']}: {value}''')
                try:
                    value = {'expect': 'single', 'expect_same': 'multi', 'expect_enum': 'single_enum'}[value[0]]
                except KeyError:
                    raise CheckException(f'''Unexpected expectation type for check {check['id']}: {value[0]}''')
            if isinstance(value, str):
                value = value.strip()
            setattr(self, Check._attribute_table[key], value)   # value is always None, str or list

            gatherers = set(Check._retrieve_attributes(check, ['facts[].gatherer'])['facts[].gatherer'])
            if gatherers.issubset(Check._valid_gatherers):
                self.tcsc_support = 'yes'
            elif gatherers.issubset(Check._known_gatherers):
                self.tcsc_support = 'no'
            else:
                self.tcsc_support = 'unknown'
                
class CheckException(Exception):
    pass       