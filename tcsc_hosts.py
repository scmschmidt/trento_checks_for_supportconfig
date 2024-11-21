#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the hosts container stack.
"""


import docker
import time
import subprocess
from typing import List, Dict, Any, Tuple, Set

import docker.models
import docker.models.containers
from tcsc_config import *


class HostsStack():
    """Represents a Hosts container stack.
    
        - self._docker (docker.DockerClient):  Instance of DockerClient.
        - self.timeout (int):  Timeout for Docker and host operations.
        - self.start_timeout (int):  Timeout for containers to start and stay alive.
        - self.id (str):  UUID of this tcsc installation.
        - self.image (str):  Image used for hosts container.
        
    """

    def __init__(self, config: Config) -> None:
        self._docker: docker.DockerClient = docker.from_env()
        self.timeout = config.docker_timeout
        self.start_timeout = config.startup_timeout
        self.id = config.id
        self.image = config.hosts_image
        self.host_label = config.hosts_label

    def _wait4start(self, host: docker.models.containers.Container):
        """Waits until given container is running and stays running."""
    
        start_time = time.time()    
        while True:
            host.reload()
            if host.status == 'running':
                break
            if  (time.time() - start_time) > self.start_timeout: 
                raise HostsException(f'Start timeout of {self.start_timeout}s reached. "{host.name}" did not became operational.')
            time.sleep(.2)

        start_time = time.time()    
        while (time.time() - start_time) <= self.start_timeout:
            host.reload()
            if host.status != 'running':
                raise HostsException(f'"Start timeout of {self.start_timeout}s reached. {host.name}" stopped running.')
            time.sleep(.2)

    def create(self, hostgroup: str, name: str, host_description: Dict) -> str:
        """Creates and starts a new host container for the requested group and returns its name."""

        dbus_uuid, agent_id = self._generate_id()
        
        supportconfig_path = host_description['supportconfig']
        supportconfig_name = os.path.basename(supportconfig_path)

        host = self._docker.containers.run(
            image = self.image,
            name = f'tcsc-host-{hostgroup}-{name}-{self.id}',
            command = '/sc/startup',
            environment = {'SUPPORTCONFIG' : f'/{supportconfig_name}',
                           'MACHINE_ID': dbus_uuid
                          },
            volumes = [f'{supportconfig_path}:/{supportconfig_name}'],
            network = 'trento_checks_for_supportconfig_default',
            labels = {'com.suse.tcsc.stack': 'host',
                      'com.suse.tcsc.hostgroup': hostgroup,
                      'com.suse.tcsc.hostname': name,
                      'com.suse.tcsc.supportfiles': supportconfig_path,
                      'com.suse.tcsc.supportconfig': supportconfig_path,
                      'com.suse.tcsc.uuid': self.id,
                      'com.suse.tcsc.agent_id': agent_id
                     },
            detach = True)
        self._wait4start(host)
        
        return host.name

    def start_hostgroup(self, hostgroup: str) -> bool:
        """Starts all hosts of given host group and returns the success."""

        for container in self.filter_containers(filter={'hostgroup': hostgroup}):
            container['container'].start()
            self._wait4start(container['container'])

        return True

    def stop_hostgroup(self, hostgroup) -> List[str]:
        """Stops all running host containers of the given host group and returns the names of the stopped containers."""

        stopped: List[str] = []
        for container in [c for c in self.filter_containers(filter={'hostgroup': hostgroup}) if c['status'] in ['running']]:
            stopped.append(container['name'])
            container['container'].stop(timeout=self.timeout)
        
        return stopped     
            
    def remove_hostgroup(self, hostgroup) -> List[str]:
        """Removes all host containers of the given host group and returns the names of the destroyed containers."""
        
        removed: List[str] = []
        for container in [c for c in self.filter_containers(filter={'hostgroup': hostgroup})]:
            removed.append(container['name'])
            container['container'].remove(v=True, force=True)        
        return removed    

    def logs(self, containername: str) -> List[str]:
        """Retrieves log for given container name."""
        
        container = self.filter_containers(filter={'name': containername})
        if container:
            return container[0]['container'].logs().decode("utf-8").strip().split(os.linesep)
        return None

    @property
    def containers(self) -> List[Dict[str, str]]:
        """Retrieves all current host containers from Docker and returns a data dictionary.""" 
        
        return [{'name': container.name or '-', 
                 'container_id': container.id,
                 'container_short_id': container.short_id,
                 'supportfiles': container.labels.get('com.suse.tcsc.supportfiles') or '-',
                 'supportconfig': container.labels.get('com.suse.tcsc.supportconfig') or '-',
                 'hostgroup': container.labels.get('com.suse.tcsc.hostgroup') or '-',
                 'hostname': container.labels.get('com.suse.tcsc.hostname') or '-',
                 'status': container.status or 'unknown',
                 'agent_id': container.labels.get('com.suse.tcsc.agent_id') or '-',
                 'container': container
                } for container in
                self._docker.containers.list(all=True, filters={'label': [self.host_label, f'com.suse.tcsc.uuid={self.id}']}) 
               ]

    def filter_containers(self, filter: Dict[str, Any] = {}, sortkey: str = 'hostgroup') -> List[Dict[str, str]]:
        """Retrieve and return current host containers matching the filter from Docker.
        Currently supported filters: 
            - hostgroup: List[str]
            - name: List[str]
        A sort key can be given to sort the results (default: hostgroup).""" 

        containers: List[str, str] = []
        for container in self.containers:
            if filter.get('hostgroup') and container['hostgroup'] != filter.get('hostgroup'):
                continue
            if filter.get('name') and container['name'] != filter.get('name'):
                continue
            containers.append(container)
        return sorted(containers, key=lambda x: x[sortkey])
    
    def _generate_id(self) -> Tuple[str]:
        """Return a generated dbus uuid by calling `dbus-uuidgen` and the derived trento-agent id."""
        
        try:
            dbus_uuid = subprocess.run(['dbus-uuidgen'],
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.STDOUT
                                        ).stdout.decode('utf-8').strip()
            agent_id = subprocess.run(['uuidgen', 
                                       '-N', dbus_uuid, 
                                       '-n', 'fb92284e-aa5e-47f6-a883-bf9469e7a0dc', 
                                       '--sha1'
                                       ],
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.STDOUT
                                    ).stdout.decode('utf-8').strip()
        except Exception as err:
            raise HostsException(f'Error generating IDs for D-Bus and Trento agent: {err}')

        return dbus_uuid, agent_id
        
    @property
    def hostgroups(self) -> Set[str]:
        """Returns all current host groups."""
        
        return set([c['hostgroup'] for c in self.filter_containers()])
    
    
class HostsException(Exception):
    pass

