# trento_checks_for_supportconfig

Makes Trento checks usable for support cases by using them on supportconfigs. Also `jq` is needed by the scripts to parse JSON.

## Prerequisites

You need `docker` and `docker-compose` installed to run containers.


## Setup Wanda

We don't need a full-fledged Trento, just the Wanda component: https://github.com/trento-project/wanda/tree/main, which
contains the Trento checks and the checks engine. Setting it up, comes down to:

```
> git clone https://github.com/trento-project/wanda.git
...
> cd wanda
> docker-compose -f docker-compose.checks.yaml up -d
...
```
> :exclamation: To be sure, that this procedure is still valid, read the `README.md` of the Wanda project.

Now Wanda should be ready and listen on port 4000/tcp! 

```
> docker ps
CONTAINER ID   IMAGE                                         COMMAND                  CREATED       STATUS             PORTS                                                                                                                                                 NAMES
1ea1fbdb1e78   ghcr.io/trento-project/trento-wanda:rolling   "/bin/sh -c '/app/bi…"   3 weeks ago     Up 15 minutes   0.0.0.0:4000->4000/tcp, :::4000->4000/tcp                                                                                                             wanda-wanda-1
3575af9d60c7   rabbitmq:3.10.5-management-alpine             "docker-entrypoint.s…"   3 weeks ago     Up 15 minutes   4369/tcp, 5671/tcp, 0.0.0.0:5672->5672/tcp, :::5672->5672/tcp, 15671/tcp, 15691-15692/tcp, 25672/tcp, 0.0.0.0:15672->15672/tcp, :::15672->15672/tcp   wanda-rabbitmq-1
a6f652bee18f   postgres:latest                               "docker-entrypoint.s…"   3 weeks ago     Up 15 minutes   0.0.0.0:5434->5432/tcp, :::5434->5432/tcp                                                                                                             wanda-postgres-1


> sudo ss -nlp sport 4000
Netid   State    Recv-Q   Send-Q     Local Address:Port     Peer Address:Port  Process                                    
tcp     LISTEN   0        512              0.0.0.0:4000          0.0.0.0:*      users:(("docker-proxy",pid=16505,fd=4))   
tcp     LISTEN   0        512                 [::]:4000             [::]:*      users:(("docker-proxy",pid=16513,fd=4))

> curl http://localhost:4000/api/readyz
{"ready":true}
```
> :bulb: To make the Wanda containers start automatically with `dockerd`, execute `docker update --restart always wanda_wanda_1 wanda_postgres_1 wanda_rabbitmq_1`.

To start and stop the Wanda containers you can use the provided scripts `start_wanda` and `stop_wanda`

### Removing and Updating

To remove the containers, call `docker-compose -f docker-compose.checks.yaml down` in the project directory. 

When updating, remove the containers and also delete the images and volumes, pull the git repo and call `docker-compose` again:

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

> docker volume rm wanda_pg_data
...

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

### Premium Checks and Custom Checks

Trento differentiates between community checks which are part of the GitHub repo and premium checks, which are located in https://gitlab.suse.de/trento-project/wanda-premium-checks (Access to SUSE Engineering VPN required!). 

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


# Inspect a supportconfig

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

If they are not there, then Wanda is not running or the `trento-agent` could not connect to Wanda for other reasons. 

See section [Troubleshooting](#Troubleshooting) below, if the container terminates immediately or does not work as expected.


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

### `PASS`, `FAIL`, `WARN` and `SKIP`
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

> :exclamation: **If a check is not meant for a provider, it is currently not filtered out. This needs to be added in the future, so false negatives can occur. Make sure, you use the matching provider for the supportconfig!**

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

> :bulb: All the information like descriptions, expectations, remediation, etc. comes directly from the check and is retrieved from Wanda without further processing.

If you a check does not match a given category or type, then you will get skipped checks:

```
0B0F87 - Installed SAPHanaSR version is identical on all nodes
  [SKIP]  Skipping check 0B0F87. Type "multi" instead of "single".
```

### `ERROR`

If something is wrong with Wanda or the check, you get errors. Let's walk through some examples.

- **The check does not exist.** 

  ```
  33B87B - 
    [ERROR] rabbiteer: Error parsing response checking execution 5884cf8d-94c2-4cf6-907b-c48e85b499bf: 'error'
  Response was: {"errors":[{"detail":"No checks were selected.","title":"Unprocessable Entity"}]}
  ```
  The name of the check is not displayed. It should be after the Id and the dash in the first line. \
  This is an indicator, that the check is in `.valid_checks` but not present in `priv/catalog` of Wanda.
  Reasons can be:
    - You have forgotten to add the premium checks ([Premium Checks and Custom Checks](#Premium-Checks-and-Custom-Checks))
    - You have updated your local Wanda and either the premium checks have been deleted or a check actually has been retracted.


- **The check has a bug**

  ```
  DE74B2 - Azure Fence agent configuration parameters are correct
    [ERROR] rabbiteer: Mandatory key "target_type" is not part of metadata of check DE74B2.
  This is a bug in the check
  ```
  Most likely changes in the API or check format have been made, but the check itself has not been updated yet. This proof-of-value uses the development repos of Trento, so those things can happen.
  

- **Wrong provider**

  ```
  C3166E - SBD version is not the recommended value
    [ERROR] rabbiteer: Error parsing response checking execution e6f0668f-db9f-4b4a-bbb2-3d4d44c8265d: 'error'
  Response was: {"errors":[{"detail":"No checks were selected.","title":"Unprocessable Entity"}]}
  ```

  If you get an `"Unprocessable Entity"` error, you should first check, if the given provider matches the host.
  Some checks (like the SBD one in this example) are only valid on for certain providers (e.g. AWS) and do not work on others. Trento's discovery prevents the executions of those checks. This is not (yet) implemented here.


- **Anything else...**

  ```
  BA215C - corosync.conf files are identical across all nodes
    [ERROR] rabbiteer: Error parsing response checking execution 3fc37483-28e3-4d19-9407-a50d74968761: 'error'
  Response was: {"errors":[{"detail":"No checks were selected.","title":"Unprocessable Entity"}]}
  ```

  Wanda is not very chatty in regards of error messages. If you get an `"Unprocessable Entity"` error and the cause is not a wrong provider, then the most probable cause is an incompatibility. Something in the check or the Wanda API has changed and the checks or tools (like `rabbiteer.py`) are not up to date yet. Trento is very active.
  Try to update everything: Wanda, this project and `rabbiteer.py`. If this does not help, create an issue. 


## Stop Container for supportconfig

If you have done your work, just stop the containers by running:

```
> ./stop_container 
Container "tcsc_1" stopped.
Container "tcsc_2" not running.
```

This will stop **all** supportconfig containers listed in `.container_def`.

# Some Technical Background

The image `sc_runner` for the supportconfig container is built from `Dockerfile`. It fetches an OpenLeap 15.4 image, adds the development repo for trento, install needed packages and added the `split-supportconfig` script from https://github.com/SUSE/supportconfig-utils.

If a container gets started from that image by `./start_container` the subdirectory `sc/` as well as the given supportconfig archive is mounted into the container. \
The directory `sc/` contains:

- `agent-config.yaml` \
  Configuration file for the `trento-agent`.
- `cibadmin` \
  Command replacement for `cibadmin`, which only supports the options `--query --local` and then simply prints the content of `/var/lib/pacemaker/cib/cib.xml`.
- `sbd` \
  Command replacement for `sbd`, which only supports dumping the header (`-d ... dump`). It prints the dumps created by `startup` form `ha.txt` of the supportconfig.
- `startup` \
  Startup script executed when the container is started. It:
    - sets `/etc/machine-id`,
    - extracts and splits the supportconfig into files (https://github.com/SUSE/supportconfig-utils/blob/master/bin/split-supportconfig),
    - copies relevant extracted files into the rootfs,
    - copies the command replacements from `sc/` into the roots,
    - creates sbd header dumps from `ha.txt`,
    - creates and installs empty RPM packages with the version info from `rpm.txt` for selected packages
    - and finally starts the `trento-agent`.

For each container an entry must be present in `.container_def`. The file contains comments explaining the details.

The primary configuration file for `run_checks` is `.valid_checks`. See the comments for details. Important is, that a check must be listed there to be available for `run_check`.


# Troubleshooting

- If a supportconfig container stops all by itself, the `trento-agent` died. If this happens directly after starting the container, the agent could not connect to Wanda. Check if all the Wanda containers are running and are fine. \
You also can start the container in the foreground with `./start_container --fg SUPPORTCONFIG` to see the logs.

- If a supportconfig container starts, but the checks don't work, you can watch the logs with `docker log [-f] CONTAINER` or enter the running container with: `docker exec -it CONTAINER /bin/bash`. \
Inside the container run `trento-agent facts gather --gatherer GATHERER` to see if the data collection works. The  get a list of available gatherers, run `trento-agent facts list`. Documentation can be found here: https://www.trento-project.io/wanda/gatherers.html

- If all checks return the same error message or time out, but the supportconfig container is running, then most certainly something has changed in Wanda or the agent. Trento is an active project and changes happen often. You should try:

  - Get the latest version of `rabbiteer.py`: (https://gitlab.suse.de/trento-project/robot-tests-for-trento-checks/-/raw/main/utils/rabbiteer.py)
  - Stop all Wanda containers and delete images **and** volumes and deploy Wanda again: [Setup Wanda:Removing and Updating](#Removing-and-Updating)
  - Rebuild the supportconfig container to get the latest agent: `docker build -t sc_runner`

# Which Gatherer Will Work?

For a check to work, the called gatherer must work with the confinements of the container. basically we have two hurdles:

1. The data must part of the supportconfig or the project must be extended to consume more input data.
2. The gatherer must retrieve the data in the ways the programmer has intended it. 

This chapter contains an evaluation for the gatherers (December 2023).

## `cibadmin`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/cibadmin.go \
**Chances: :slightly_smiling_face:**

Works by providing a script as `cibadmin` command, which returns `/var/lib/pacemaker/cib/cib.xml` (`ha.txt`) when called with `--query --local`

## `corosync.conf`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/corosyncconf.go \
**Chances: :slightly_smiling_face:**

Works by providing `/etc/corosync./corosync.conf` (`ha.txt`) in the container rootfs.

## `corosync-cmapctl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/corosynccmapctl.go \
**Chances: :frowning_face:**

The gatherer is calling `corosync-cmapctl -b`, which therefore must work. With the corosync object database being an in-memory non-persistent database, checks using that gatherer won't work as long as a dump of the corosync object database is not part of the supportconfig (or provided otherwise).

## `dir_scan`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/dir_scan.go \
**Chances: :neutral_face:**

The gatherer scans directories with a glob pattern provided as argument and returns a list of files matched by the pattern with group/user information associated to each file. Only such checks would work, which address directories/files provided by the supportconfig. **It depends therefore on the check if it will work or not.**

## `disp+work`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/dispwork.go \
**Chances: :frowning_face:**

With calling the `disp+work` command to get compilation_mode, kernel_release and patch_number checks will not work. This data is not part of the supportconfig. To get it to work additional information must be provided as well as a `disp+work` replacement, which presents the data in the same way as the original `disp+work`.

## `fstab`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/fstab.go \
**Chances: :slightly_smiling_face:**

Works by providing `/etc/fstab` (`fs-diskio.txt`) in the container rootfs.

## `groups`
https://www.trento-project.io/wanda/gatherers.html#groupsv1 \
**Chances: :frowning_face:**

With `/etc/groups` not part of the supportconfig, checks using this gatherer won't work.

## `host`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/hostsfile.go \
**Chances: :slightly_smiling_face:**

Works by providing `/etc/hosts` (`env.txt`) in the container rootfs.

## `mount_info` 
https://www.trento-project.io/wanda/gatherers.html#groupsv1 \
**Chances: :frowning_face:**

The gatherer will most probably not work. It relies on https://github.com/moby/sys/tree/main/mountinfo to get the mount information. It has to be checked how the project is doing it, but if it accesses `/proc` it can become difficult to provide the supportconfig data. 

Also `blkid DEVICE -o export` will be called by the gatherer. The original command must be replaced by a script presenting the output of `blkid` (`fs-diskio.txt`) in the way the gatherer expects it.

## `os-release`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/osrelease.go \
**Chances: :slightly_smiling_face:**

Works by providing `/etc/os-release` (`basic-environment.txt`) in the container rootfs.

## `package_version`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/packageversion.go \
**Chances: :slightly_smiling_face:**

Works by providing an empty on-the-fly created RPM package from `rpm.txt`.

## `passwd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/passwd.go \
**Chances: :frowning_face:**

With `/etc/passwd` not part of the supportconfig, checks using this gatherer won't work.

## `products`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/products.go \
**Chances: :frowning_face:**

With only the file list of `/etc/products.d/` but not the content of those files part of the supportconfig, checks using this gatherer won't work.

## `sapcontrol`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapcontrol.go \
**Chances: :frowning_face:**

This is a complex gatherer and from reading the description it uses a unix socket connection with `/tmp/.sapstream5xx13`.
Besides the fact, that those data is not part of the supportconfig, this approach would require to write a program that present the data via a socket to the gatherer.

## `saphostctrl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/saphostctrl.go \
**Chances: :frowning_face:**

Executes `/usr/sap/hostctrl/exe/saphostctrl -function FUNCTION`. Regardless which functions are supported, the data is not part of the supportconfig. For checks to work the required data/dumps must be provided by other means.

## `sap_profiles`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapprofiles.go \
**Chances: :frowning_face:**

Returns content of `/sapmnt/<SID>/profile` which is not part of the supportconfig.

## `sapinstance_hostname_resolver`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapinstancehostnameresolver.go \
**Chances: :frowning_face:**

Th gatherer needs to be investigated further, but the required data is not part of the supportconfig.

## `sapservices`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapservices.go \
**Chances: :frowning_face:**

Presents `/usr/sap/sapservices` which is not part of the supportconfig.

## `saptune`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/saptune.go \
**Chances: :slightly_smiling_face:**

Calls `saptune` command with limited set of commands. It should be possible to provide a script which returns the information extracted from files of `plugin-saptune.txt`.

## `sbd_config`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sbd.go \
**Chances: :slightly_smiling_face:**

Works by providing `/etc/sysconfig/sbd` (`ha.txt`) in the container rootfs.

## `sbd_dump`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sbddump.go \
**Chances: :slightly_smiling_face:**

Works by having a `sbd` script which returns the expected output from `sbd -d <device> dump` by processing the sbd dumps of `ha.txt`.

## `sysctl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sysctl.go \
**Chances: :slightly_smiling_face:**

The gatherer executes `sysctl -a` which is part of the supportconfig. Just a script named `sysctl` is needed which returns that part of `env.txt`.

## `systemd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/systemd_v2.go \
**Chances: :neutral_face:**

The gatherer connects to `dbus` to communicate with `systemd`. For checks to work, the container needs a `dbus` and a fake `systemd` answering the questions of the gatherer from the supportconfig.

## `verify_passwd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/verifypassword.go \
**Chances: :frowning_face:**

The command `getent shadow USER` must work. Since the supportconfig does not contain `/etc/shadow` or a dump of the user`s password hashes, checks using this gatherer will not work.

# To Do (if this PoV hits a nerve)

- Updating the project with new checks. Trento is growing.
- Enable existing checks which currently can not be used, because they run commands on active clusters.
- Make the project more user-friendly.
- ...
