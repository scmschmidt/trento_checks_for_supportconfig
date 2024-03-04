#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the hosts container stack.
"""


import docker
import random
import string
from typing import List, Dict, Any, Tuple
from tcsc_config import *


class Host():
    """Represents a host container.
    
        - self._docker (docker.DockerClient):  Instance of DockerClient.
    """
    
    def __init__(self, description: Dict[str, Any]) -> None:

        self._docker: docker.DockerClient = docker.from_env()
        
        print(description)
        c = self._docker.containers.run(**description)

class HostsStack():
    """Represents a Hosts container stack.
    
        - self._containers (Dict[str, Container]):  Dict with the Wand container instances referenced by name.
        - self._docker (docker.DockerClient):  Instance of DockerClient.
        - self.timeout (int):  Timeout for Docker and host operations.
        - self.id (str):  UUID of this tcsc installation.
        - self.image (str):  Image used for hosts container.
    """

    def __init__(self, config: Config) -> None:
        self._docker: docker.DockerClient = docker.from_env()
        self.timeout = config.docker_timeout
        self.id = config.id
        self.image = config.hosts_image
        self.host_label = config.hosts_label
        # self._containers = {container.name: container for container in 
        #                     self._docker.containers.list(all=True, filters={'label': config.wanda_label})}
        # if set(self._containers.keys()) != set(config.wanda_containers):
        #     raise HostsException('Not all required host containers are present.')

    def start(self, hostgroup: str, supportfiles: List[str]) -> Host:
        """Creates and starts a new host container for the requested group with the given supportfiles.
    
        Returns the names of the started containers."""

        host = Host({'image': self.image,
                     'name': f'''tcsc-host-{hostgroup}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}''',
                     'command': '/bin/bash',
                     'labels': {'com.suse.tcsc.stack': 'hosts', #FIXME: USE self.host_label!!!!!!! DO WE NEED THAT LABEL FREELY DEFINEABLE????
                                'com.suse.tcsc.hostgroup': hostgroup,
                                'com.suse.tcsc.supportfiles': ', '.join(supportfiles),
                                'com.suse.tcsc.uuid': self.id
                               }
                    }
                   )

        # --rm -e "MACHINE_ID=${id}" 
        # -e "SUPPORTCONFIG=${supportconfig_container}" 
        # -v ./sc:/sc -v "${supportconfig}:${supportconfig_container}" 
        # --network=trento_checks_for_supportconfig_default 
        # -t sc_runner /sc/startup > /dev/null ; then

    @property
    def container_status(self) -> List[Dict[str, str]]:
        """Returns a list with all host containers and important attributes. """
        
        return [{'name': container.name, 
                 'supportfiles': container.labels.get('com.suse.tcsc.supportfiles'),
                 'hostgroup': container.labels.get('com.suse.tcsc.hostgroup'),
                 'status': container.status
                } for container in
                self._docker.containers.list(all=True, filters={'label': self.host_label})
               ]
        

class HostsException(Exception):
    pass

