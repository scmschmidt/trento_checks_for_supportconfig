# PoV wanda-supportconfig

The goal of this prove of value is to demonstrate the value of Trento checks for support cases by using them on supportconfigs.

## Installation

You can do the installation steps manually or use the provided playbooks in `playbooks/`. If you do, create an inventory file first containing the host where you want to setup the Poc.
If this your local machine, you can skip that step, because `ansible` uses localhost as default.

```
all:
  hosts:
    <HOST>:
      ansible_host: <IP OR RESOLVABLE NAME>  # Only required, if <HOST> cannot be resolved!

```
ansible >= 2.10 !!!!
ansible-galaxy collection install community.docker


### Requirements

To run the PoV several packages and patterns are needed:

    -
    -
    -

Install them on the PoV system by your own or use the provided playbook `...`





### Installation of Wanda

We don't need a full-fledged Trento, just the Wanda component: https://github.com/trento-project/wanda/tree/main
Clone the repo and follow the instruction there, which comes down to a `docker-compose -f docker-compose.checks.yaml up -d`.

Alternatively use the provided playbook: `install_wanda.yml`


```
git clone https://github.com/trento-project/wanda.git
```


docker build -t sc_runner .


Install the 

The 

Split a supportconfig: https://github.com/SUSE/supportconfig-utils/tree/master  (bin/split-supportconfig)


https://github.com/schlosstom/GrafHana/blob/main/docker-compose.yaml


docker run -i -v /etc/machine-id:/etc/machine-id -v .:/sc --network=wanda_default -t sc_runner /bin/bash

trento-agent facts gather --gatherer "corosync.conf"