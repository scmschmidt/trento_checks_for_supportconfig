#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the tcsc configuration.
"""


import os
import json
import uuid 


class Config():
    """Represents tcsc configuration.
    
        - self.id (str):  UUID used to mark the created containers. 
        - self.wanda_containers (List[str]):  List of all Wanda container names.  
        - self.wanda_label (str):  Label used to identify Wanda containers for tcsc.
        - self.docker_timeout (int):  Timeout in seconds for docker (and Wanda) operations.
        - self.startup_timeout (int): Timeout in seconds for host containers to start and keep alive.
        - self.wanda_url (str):  URL to connect to the Wanda container.
        - self.hosts_image (str):  Name of the hosts container image .
        - self.hosts_label (str):  Label used to identify tcsc hosts container. 
        - self.wanda_autostart (bool):  Determines if Wanda shall be started automatically when required.
        - self.colored_output (bool):  Determines if the output should be colored or not.
        
    #TODO: DESCRIBE (DEFAULT) CONFIG CONTENT.
    """

    def __init__(self, configfile: str, create: bool = True) -> None:
        """Loads the configuration from `configfile`. If `create` is
        true and `configfile` does not exists, a default configuration
        will be created.

        Args:
            configfile (str):           Filename of JSON configuration.
            create (bool, optional):    Flag if a default configuration shall be created,
                                        if the config file is missing. Defaults to True.
        """

        configfile = os.path.realpath(os.path.expandvars(os.path.expanduser(configfile)))
        try:
            if not os.path.exists(configfile) and create:
                dir, _ = os.path.split(configfile)
                if dir:
                    os.makedirs(dir, mode=0o700, exist_ok=True)
                with open(configfile, 'w') as f:
                    f.write(json.dumps({
                                       'id': str(uuid.uuid1()),
                                       'wanda_containers': ['tcsc-rabbitmq', 'tcsc-postgres', 'tcsc-wanda'],
                                       'wanda_label': 'com.suse.tcsc.stack=wanda',
                                       'hosts_label': 'com.suse.tcsc.stack=host',
                                       'docker_timeout': 10,
                                       'startup_timeout': 3,
                                       'wanda_url': 'http://localhost:4000',
                                       'hosts_image': 'tscs_host',
                                       'wanda_autostart': True,
                                       'colored_output': True
                                       }, indent=4
                                       )
                            )
            with open(configfile) as f:
                config = json.load(f)
                self.id = config['id']
                self.wanda_containers = config['wanda_containers']
                self.wanda_label = config['wanda_label']
                self.hosts_label = config['hosts_label']
                self.docker_timeout = abs(int(config['docker_timeout']))
                self.wanda_url = config['wanda_url']
                self.hosts_image = config['hosts_image']
                self.startup_timeout = config['startup_timeout']
                self.wanda_autostart = config['wanda_autostart']
                self.colored_output = config['colored_output']
        except Exception as err:
            raise ConfigException(f'Error accessing configuration: {err}')


class ConfigException(Exception):
    pass

