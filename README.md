# trento_checks_for_supportconfig

Makes Trento checks usable for support cases by using them on supportconfigs.

[[_toc_]]

## Prerequisites

You need `docker` and `docker-compose` installed to run containers.


## Setup Wanda

We don't need a full-fledged Trento, just the Wanda component: https://github.com/trento-project/wanda/tree/main, which
contains the Trento checks and the checks engine. Setting it up, comes down to:

```
git clone https://github.com/trento-project/wanda.git
cd wanda
docker-compose -f docker-compose.checks.yaml up -d
```
> :exclamation: To be sure read the `README.md` of the Wanda project, if there are any changes to the procedure!

Now Wanda should be ready and listen on port 4000/tcp! 

```
> docker ps
CONTAINER ID   IMAGE                                         COMMAND                  CREATED       STATUS             PORTS                                                                                                                                                 NAMES
90f939b65da8   ghcr.io/trento-project/trento-wanda:rolling   "/bin/sh -c '/app/bi…"   3 weeks ago   Up 19 minutes      0.0.0.0:4000->4000/tcp, :::4000->4000/tcp                                                                                                             wanda_wanda_1
d4eeb7e2f222   rabbitmq:3.10.5-management-alpine             "docker-entrypoint.s…"   3 weeks ago   Up 19 minutes      4369/tcp, 5671/tcp, 0.0.0.0:5672->5672/tcp, :::5672->5672/tcp, 15671/tcp, 15691-15692/tcp, 25672/tcp, 0.0.0.0:15672->15672/tcp, :::15672->15672/tcp   wanda_rabbitmq_1
9bd4216f6d33   postgres:latest                               "docker-entrypoint.s…"   3 weeks ago   Up 19 minutes      0.0.0.0:5434->5432/tcp, :::5434->5432/tcp                                                                                                             wanda_postgres_1

> sudo ss -nlp sport 4000
Netid   State    Recv-Q   Send-Q     Local Address:Port     Peer Address:Port  Process                                    
tcp     LISTEN   0        512              0.0.0.0:4000          0.0.0.0:*      users:(("docker-proxy",pid=16505,fd=4))   
tcp     LISTEN   0        512                 [::]:4000             [::]:*      users:(("docker-proxy",pid=16513,fd=4))

> curl http://localhost:4000/api/readyz
{"ready":true}
```
> :bulb: To make the Wanda containers start automatically with `dockerd`, execute `docker update --restart always wanda_wanda_1 wanda_postgres_1 wanda_rabbitmq_1`.

> To start and stop the Wanda containers run `docker start wanda_wanda_1 wanda_postgres_1 wanda_rabbitmq_1` and `docker stop wanda_wanda_1 wanda_postgres_1 wanda_rabbitmq_1` respectively.

### Removing and Updating

To remove the containers call `docker-compose -f docker-compose.checks.yaml down` in the project directory. 

When updating, remove the containers and also delete the images, pull the git repo and call `docker-compose` again:

```
> docker-compose -f docker-compose.checks.yaml down
Stopping wanda_wanda_1    ... done
Stopping wanda_rabbitmq_1 ... done
Stopping wanda_postgres_1 ... done
Removing wanda_wanda_1    ... done
Removing wanda_rabbitmq_1 ... done
Removing wanda_postgres_1 ... done
Removing network wanda_default

> docker image rm ghcr.io/trento-project/trento-wanda:rolling postgres:latest rabbitmq:3.10.5-management-alpine
...
Deleted: sha256:43dcc2f3a056abd441bd4a46b75fe3bc37d83a0d48eabe5367b761d5c28cc668
Deleted: sha256:24302eb7d9085da80f016e7e4ae55417e412fb7e0a8021e95e3b60c67cde557d

> cd wanda
> git pull
...

> docker-compose -f docker-compose.checks.yaml up -d
Creating network "wanda_default" with the default driver
Pulling rabbitmq (rabbitmq:3.10.5-management-alpine)...
3.10.5-management-alpine: Pulling from library/rabbitmq
...
Creating wanda_postgres_1 ... done
Creating wanda_rabbitmq_1 ... done
Creating wanda_wanda_1    ... done
```

### Premium checks and custom checks

Trento differs between community checks which are part of the GitHub repo and premium checks are located in https://gitlab.suse.de/trento-project/wanda-premium-checks. 

To add the premium checks, copy the files from `https://gitlab.suse.de/trento-project/wanda-premium-checks/-/tree/main/priv/catalog` into `priv/catalog/` of the Wanda project directory.

You can put your own checks in `priv/catalog/` as well, if you know how to write them (https://www.trento-project.io/wanda/specification.html#introduction).

> :bulb: The directory `wanda/priv/catalog/` is mounted into the container. Any changes are immediately visible to Wanda. It is not necessary to restart or rebuild the container.


## Setup this project.

Leave the Wanda project directory, clone this repo and enter the project directory: 

```
git clone https://github.com/scmschmidt/trento_checks_for_supportconfig.git
cd trento_checks_for_supportconfig
```

##  Build the supportconfig container image

Run:
 ```
 docker build -t sc_runner .
 ```
 
 If the build process was successful, a `docker images` should list the image:

```
REPOSITORY    TAG       IMAGE ID       CREATED         SIZE
sc_runner     latest    01d133a6ca5f   3 hours ago     842MB
...
```
That's it!


# Inspect a supportconfig.

## Start Container for supportconfig
You have to start one container per supportconfig. Having multiple containers makes sense, if 

- you want inspect multiple supportconfigs in one step or 
- if you have supportconfigs of a cluster. 

Some Trento checks (labeled as `multi`) compare settings of cluster nodes and therefore require all supportconfigs of that cluster at the same time. 

The syntax is: `./start_container SUPPORTCONFIG...`

> :bulb: For each container you need one entry in `.container_def`. Currently two entries are prepared.

> :exclamation: Always call `start_container` from the project directory. The subdirectory `sc/` gets mounted into the container.

```
# ./start_container ~/Cases/00999999/scc_vmhana01_231011_1528.txz 
Container "tcsc_1" started for supportconfig "/home/sschmidt/Cases/00999999/scc_vmhana01_231011_1528.txz".
```

You can check with `docker ps` if the containers are running:

```
# docker ps
CONTAINER ID   IMAGE       COMMAND          CREATED          STATUS          PORTS     NAMES
627061cabfc8   sc_runner   "/sc/startup"    23 minutes ago   Up 23 minutes             tcsc_1
...
```

If they are not there, then Wanda is not running or the `trento-agent` could not connect to Wanda for other reasons. \
To debug you can start the container in the foreground with: `./start_container --fg SUPPORTCONFIG`

To check the logs of a running container, run `docker log [-f] CONTAINER`, eg.  `docker logs tcsc_1`.


## Run the Checks

Now simply run the checks: `./run_checks PROVIDER CATEGORY|all TYPE:all [CHECK...]`

- `PROVIDER`\
  Either `default`, `kvm`, `azure` or `gcp`. \
  Depending on the infrastructure the checks expect different settings or may not run at all.
  Chose the correct value depending on the system where the supportconfig is coming from.

- `CATEGORY`\
  Either `corosync`, `sbd`, `package` or `all`.
  An arbitrary grouping of the checks to make it easier to run subsets of them. The available
  categories depend on the third column of `.valid_checks`.

- `TYPE`\
  Either `single`, `multi` or `all`.
  Single checks get executed on each supportconfig individual, multi checks on all supportconfigs
  simultaneously. The check defines the type. Multi checks are mostly meant to verify if certain settings are identical on all cluster nodes. \
  Types depend on the third column of `.valid_checks`.

- `CHECK`\
  You can further restrict the amount of executed checks by simply list them on the command line.

> :exclamation: If you don't have added the premium checks when setting up Wanda, you have to comment them out in the `.valid_checks` file.

Example:
```
./run_checks default all all
```

## Check Results

If everything is ok, then a check will pass:

```
C620DC - Corosync `expected_votes` is set to expected value
  [PASS]  tcsc_1
    Expectations: expected_votes: true
    Should      : expected_expected_votes=2
    Is          : corosync_expected_votes=2
```

If a check fails:

```
A1244C - Corosync `consensus` timeout is set to expected value
  [FAIL]  tcsc_1
    Expectations: consensus_timeout: false
    Should      : expected_consensus_timeout=6000
    Is          : corosync_consensus_timeout=36000
    Remediation : ## Abstract
                  The value of the Corosync `consensus` timeout is not set as recommended. 
                   
                  ## Remediation 
                  Adjust the corosync `consensus` timeout as recommended on the best practices, 
                  and reload the corosync configuration 
                   
                  1. Set the correct `consensus` timeout in the `totem` section in the corosync 
                  configuration file `/etc/corosync/corosync.conf`. This action must be repeated
                  in all nodes of the cluster. 
                  ...

                  ## References 
                  Azure: 
                   
                  - https://docs.microsoft.com/en-us/azure/virtual-machines/workloads/sap/high-availability-guide-suse-pacemaker#install-the-cluster 
                  ...
```

you not only get the expected and found value, but also an explanation how to fix the problem as well as references to the official documentation.

> :exclamation: **If a check is not meant for a provider, it is currently not filtered out! This needs to be added in the future, so false negatives can occur!**

Similar to a fail is a warning. If a check is reporting a warning, then the deviation is not critical, but the customer should act:

```
DA114A - Corosync has at least 2 rings configured
  [WARN]  tcsc_1
    Expectations: expected_number_of_rings_per_node: false
                  has_some_nodes_configured: true 
    Should      : expected_corosync_rings_per_node=2
    Is          : corosync_nodes=[{"nodeid":1,"ring0_addr":"10.0.1.10"},{"nodeid":2,"ring0_addr":"10.0.2.11"}]
    Remediation : ## Abstract
                  It is strongly recommended to add a second ring to the corosync communication. 
                   
                  ## References 
                  Azure: 
                   
                  - https://docs.microsoft.com/en-us/azure/virtual-machines/workloads/sap/high-availability-guide-suse-pacemaker 
                  ...

```

If a check throws an error, this can have multiple reasons.

```
BA215C - corosync.conf files are identical across all nodes
  [ERROR] rabbiteer: Error parsing response checking execution 3fc37483-28e3-4d19-9407-a50d74968761: 'error'
Response was: {"errors":[{"detail":"No checks were selected.","title":"Unprocessable Entity"}]}
```
((TBD))


> :bulb: All the information like descriptions, expectations, remediation, etc. comes directly from the check and is retrieved from Wanda without further processing.


## Stop Container for supportconfig

If you have done your work, just stop the containers by running:

```
> ./stop_container 
Container "tcsc_1" stopped.
Container "tcsc_2" not running.
```

This will stop **all** supportconfig containers listed in `.container_def`.

# Tools from different repos

Currently two tools are part of this repos, which are simply copied from other repos.
- `rabbiteer.py` \
  This repo contains a version of `rabbiter.py` from https://gitlab.suse.de/trento-project/robot-tests-for-trento-checks and is located in `utils/`. \
  In case of problems with newer Wanda versions, try a more recent version if its available.

- `split-supportconfig` \
  To split a supportconfig text file into real files `(bin/split-supportconfig` of the https://github.com/SUSE/supportconfig-utils/tree/master is used.


# Troubleshooting

- If a supportconfig container stops all by itself, the `trento-agent` died. If this happens directly after starting the container, the agent could not connect to Wanda. Check if all the Wanda containers do run and are fine.

- If a supportconfig container starts, but the checks don't work, enter the container and take a look at the logs:

  ```
  # docker exec -it tcsc_1 /bin/bash
  627061cabfc8:/ # cat /var/log/startup.log 
  /scc_vmhana01_231011_1528/etc.txt
      splitting to etc/iscsid.conf
      splitting to etc/yp.conf
      ...

  627061cabfc8:/ # cat /var/log/trento-agent
  time="2023-10-13 15:08:19" level=info msg="Using config file: /sc/agent-config.yaml"
  time="2023-10-13 15:08:19" level=info msg="Starting the Console Agent..."
  ...
  ```

- If all checks return the same error message or time out and the supportconfig container is there, then most certainly something has changed in Wanda or the agent. Trento is a very active project and changes happen often. One thing you should try:
  1. Get the latest version of `rabbiteer.py`.
  1. Stop all Wanda containers and delete images **and** volumes!
  1. Deploy the Wanda containers again (`docker-compose -f docker-compose.checks.yaml up -d`).
  1. Rebuild the supportconfig container to get the latest agent: `docker build -t sc_runner`

# To Do (if this PoV hits a nerve)

- Updating the project with new checks. Trento is growing.
- Enable existing checks which currently can not be used, because they run commands on active clusters.
- Make the project more user-friendly.
