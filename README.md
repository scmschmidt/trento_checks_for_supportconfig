# tcsc - Trento checks for supportconfig

Makes Trento checks usable for support cases by using them on supportconfigs. 

> :bulb: This is a rewrite of the proof-of-value which final version can be found here: https://github.com/scmschmidt/trento_checks_for_supportconfig/releases/tag/pov-final

> :bulb: This project targets primary support engineers working with supportconfigs, but can also be used to assist in
  Trento check development. See [Trento Check Development](Trento%20Check%20Development.md) for details.

> :exclamation: This version works only with Wanda versions, where checks are in a separate container. 
  This should be the default since Trento 2.4.

## Prerequisites

You need `git` (optional) as well as `docker` and `docker-compose` installed to run containers.

> :bulb: The `tcsc` is containerized by default, but being a simple Python script, you can run it directly.
> You need a current Python version (3.10 and 3.11 have been tested) and have to install the `docker`, `defusedxml` and `termcolor` modules (`pip3 install docker defusedxml termcolor`).
> To make life easier create an alias `tcsc` to call your Python interpreter with the absolute path to `src/tcsc.py'` so you can run the command from everywhere.
> You also need to adapt `wanda_url` to "http://localhost:4000" in the configuration file (see [Configuration File](#configuration-file)) or provide your own config with `-c`.


## Teaser

Below follows a longish README with all the details. This might frighten you! To judge if it is worth your time, here how it could look like when you check a supportconfig after you have done the [Setup](#setup):

```
> tcsc hosts create SR006699 scc_vmhana01_231011_1528.txz scc_vmhana02_231011_1533.txz
...
> tcsc checks run SR006699 
...
> tcsc hosts remove SR006699
```

This would run all current Trento checks on the cluster's supportconfigs which apply. 




## Setup

> :exclamation: The following steps have been done on an OpenLeap 15.5, but should be similar on other distros.

Do the following  steps as root:

1. Install prerequisites.    : 
      ```
      zypper install git docker-compose-switch docker
      ```
      
1. Enable and start `docker`:
   ```
   systemctl enable --now docker.service
   ```

1. Add your user to the `docker` group:
   ```
   usermod -aG docker YOUR_USER
   ```

  > :exclamation: Don't forget to log out and log on again!

Do the following steps as normale user:

1. Clone this repo and enter the project directory (or get it otherwise): 

   ```
   git clone https://github.com/scmschmidt/trento_checks_for_supportconfig.git
   cd trento_checks_for_supportconfig
   ```

1. Run: `./install` 

   It sets up and starts the Wanda containers as well as creating the image for the supportconfig hosts. 

   > :bulb: To use a specific Wanda version set the environment variable `WANDA_VERSION`.
   > The default always uses the latest released version. For a specific one, run: `WANDA_VERSION=... ./install`
   
   > :bulb: To use a specific container registry for Wanda set the environment variable `WANDA_REGISTRY`.
   > The default always uses registry.opensuse.org/devel/sap/trento/factory/containers/trento containing the rolling release. To use a different, run: `WANDA_REGISTRY=... ./install`
   > The registry for the released version is registry.suse.com/trento.

   > :exclamation: If the personal configuration file `~/.config/tscs/config` exists, the install script puts the new one as `~/.config/tscs/config.new`.
   > Verify if changes need to be adapted.

   > :exclamation: This version works only with Wanda versions, where checks are in a separate container, which should be the default since Trento 2.4. 

1. Place the script `tcsc` in `~/bin` or `/usr/local/bin` (last requires root).


## Update

To update the entire installation:

  1. Enter the repo directory.
  1. Update the repo: `git pull`
  1. Delete the existing setup: `./uninstall`
  1. Install the updated version: `./install`

To update only a part of the stack, update the repo first with `git pull` and use the scripts
in `setup/`:

  - To update only Wanda call: `setup/uninstall_wanda && setup/install_wanda`\
    Do not forget the set the environment variables for the version and registry if needed.

  - To update the host container call `setup/uninstall_host && setup/install_host`

  - To update the command container call `setup/uninstall_cmd && setup/install_cmd`

> :warning: An uninstallation removes the containers, images and volumes.

> :exclamation: After a `git pull` do not forget to update the `tcsc` script in `~/bin`, `/usr/local/bin` or wherever you put it. 

> :wrench: The host and command containers can be build locally. To do so use the scripts `setup/install_host_local` and `setup/install_cmd_local`. Remove the ones pulled from the GitHub registry first by calling `setup/uninstall_host` and `setup/uninstall_cmd`.

## Removal

To remove all containers, images, volumes and networks, call: `./uninstall` and delete the `tcsc` script in `~/bin`, `/usr/local/bin` or wherever you put it. 


## Inspect a supportconfig

The tool to work with, is `tcsc`. It can

  - manage the Wanda stack,
  - manage the required supportconfig containers
  - list and execute the checks.


### Manage Wanda

To inspect a supportconfig, the Wanda stack must be running. To verify the status, run:
```
tcsc wanda status
```
If you get the output `Wanda is operational` everything is fine.
> :bulb: Per default `tcsc` starts Wanda automatically if needed. 
> This can be changed by setting `wanda_autostart` in `~/.config/tcsc/config`. 
> See [Configuration File](#configuration-file) for details.

> :bulb: It is normal, that the `tcsc-trento-checks` container always reports
> as exited. The container just exists to provide a volume with the Trento checks.

In case Wanda is not there, run:
```
tcsc wanda start
``` 

If you do not need Wanda anymore, you can stop the stack with:
```
tcsc wanda stop
``` 

### Manage Hosts (supportconfig Containers)

To run checks, for each supportconfig an individual (host) container must be started. Such a container runs the `trento-agent` inside and connects to Wanda. For Wanda the container is simply a host which shall be checked. Therefore the content of the supportconfig is placed inside the container in a way, that the `trento-agent` accepts it as system data. The idea is to "simulate" the customers setup using the support and let Wanda check it.

Currently there are two types of Trento checks. Single checks and multi checks. \
Single checks run only on one individual host, contrary to multi checks which need at least two systems (depending on the check of course) and it most cases compare settings between them. \
As consequence you should always create one host container for each host with the appropriate supportconfig if you deal with a cluster. 

To create a host container, run:
```
tcsc hosts create GROUPNAME [-e KEY=VALUE...] SUPPORTFILE...
```

- `GROUPNAME` is a free name to group hosts which belong together (e.g. cluster). This name is later used to execute checks on the hosts. Use case numbers, system names, customer names, whatever is semantic.\
In case of HA clusters, each cluster must be separate group!

- `SUPPORTFILE` is the supportconfig itself or the directory with the extracted archive.
  For each supportconfig one host container gets started.\
  In case of an HA cluster supportconfigs from **all** nodes have to be listed, otherwise some checks will fail!

- `KEY=VALUE` environment pairs contain information to Wanda normally provided by Trento internally.
  `tcsc` tries to detect these information automatically, but this might fail. Best verify them by running:
  `tcsc hosts status -d GROUPNAME` (the command will be described later) after creation. The Trento checks rely on those information and will result in false positives or false negatives, if set wrongly.  **The detection is an educated guess at best. Please verify it. If the detection was wrong, remove the group and re-create them with the correct parameters.

  The following keys are used.

  - `provider`\
    Virtualization or Cloud the system is running on. Bare metal uses `default`.\
    one of: `azure`, `aws`, `gcp`, `kvm`, `nutanix`, `vmware`, `default`, `unknown`

    > :exclamation: Currently only Nutanix does not get detected automatically.

  - `cluster_type`\
    One of `hana_scale_up`, `hana_scale_out`, `ascs_ers` in case of a HA cluster, otherwise `None`.\
    If more then one supportconfig is given, an HA cluster is assumed and the cluster type detection is done.
  
  - `ensa_version` (ASCS/ERS cluster)\
    One of `ensa1`, `ensa2`, `mixed_versions` in case of ASCS/ERS (`cluster_type` is `ascs_ers`), otherwise `None`\
    In case of a SAP HANA cluster `ensa_version` is irrelevant and always `None`. 

  - `filesystem_type` (ASCS/ERS cluster)\
    One of `resource_managed`, `simple_mount`, `mixed_fs_types` in case of ASCS/ERS (`cluster_type` is `ascs_ers`), otherwise `None`\
    In case of a SAP HANA cluster `ensa_version` is irrelevant and always `None`.

  - `architecture_type` (SAP HANA cluster)\
    One of `classic`, `angi` in case of SAP HANA (`cluster_type` is `hana_scale_up` or `hana_scale_out`), otherwise `None`\
    Only required in case of a SAP HANA HA cluster. On an ASCS/ERS cluster the value is irrelevant and always `None`.
 
  - `hana_scenario` (SAP HANA cluster)\
    One of `performance_optimized`, `cost_optimized`, `unknown`	in case of an SAP HANA ScaleUp HA cluster (`cluster_type` is `hana_scale_up`), otherwise `None`\
    Only required in case of a SAP HANA ScaleUp HA cluster. On an SAP HANA ScaleOut HA cluster or an ASCS/ERS cluster the value is irrelevant and always `None`.

  > :bulb: The environment information also can be provided/overwritten when running the checks.

Should the start of a host container fail, check the container logs (see [Troubleshooting](#Troubleshooting) below).
To get a host container at least started, the supportconfig must contain the files:
  - `basic-environment.txt`¸
  - `ha.txt`
  - `rpm.txt`
  - `plugin-ha_sap.txt`

If you do not need the host container anymore stop and destroy them with:
```
tcsc hosts stop GROUPNAME
```
and
```
tcsc hosts remove GROUPNAME
```

> :bulb: A `stop` only stops the container, but leaves the container images, so they can be started later again simply with: `tcsc hosts start GROUPNAME`. The support files are not read again.

> :wrench: Example for a HA cluster:
> ```
> tcsc hosts create ACME-HANAProd cases/47114711/scc_vmhana01_231011_1528.txz cases/47114711/scc_vmhana02_231011_1533.txz
> ```
> 
> This starts two containers, one for *scc_vmhana01_231011_1528* and one for *scc_vmhana02_231011_1533*, which
> can be addressed via *ACME-HANAProd* together. 
>
> After running checks, destroy the containers by:
> ```
> tcsc hosts remove ACME-HANAProd
> ```

Anytime you can get an overview about your running host containers with:
```
tcsc hosts status [GROUPNAME]
```

> :bulb: Use `-d` or `--detail` to get more information about the host containers, like the container id, the Trento agent id, the hostname (from the supportconfig), the hostgroup and the referenced support files (with the container hostfs mountpoint), the environment data (provider, cluster type, etc.) and the manifest (extracted information from the support files).

The supportfiles are only read once when the host container is created. A restart of an existing host container does not reread the files,
but it can be triggered with:

```
tcsc hosts rescan GROUPNAME
```

The host container must be running at that time.


### Run the Checks

To list all supported checks grouped by the Trento check group, run:
```
tcsc checks list
```

> :bulb: To also list not supported or unknown checks, use `-a` or `--all`. \
>  A check is not (yet) supported, because the information required is not part of the support files or there is not yet
>  a method implemented to prepare the data for the Trento gatherers (see [Which Gatherer Works](#which-gatherer-works) for details). \
>  An unknown check means that the gatherer used by the check is not known to `tcsc` yet.

> :bulb: Use `-d` or `--detail` to get more information about the checks, like type, supported providers and cluster types or the used gatherer.

To execute all supported checks on a group (of running host containers), run:
```
tcsc checks run GROUPNAME
```

> :wrench: All checks are executed subsequential. If you want the execution be hold when a check
> does not pass, use the option `-w`. The execution resumes if you press ENTER.

> :exclamation: Certain environment information get autodetected when creating the host group. Those settings need to be correct or the checks will result in incorrect results (See above [Manage Hosts (supportconfig Containers)](#manage-hosts-supportconfig-containers)). Current settings can be shown with `tcsc hosts status -d GROUPNAME`.
> If you do not want to re-create the hostgroup, you can override the settings using `-e KEY=VALUE...` when running the checks.

If only a limited amount of checks shall be executed, you can either provide the Trento check group:
```
tcsc checks run GROUPNAME -g GROUP
```
or the check id:
```
tcsc checks run GROUPNAME -c CHECK
```

> :wrench: To have more then one group or check, use `-g` or `-c` multiple times.

> :wrench: To see only checks, which have not passed, add the option `-f`.

> :wrench: Skipped checks are only shown with `-s`.
A check can have the following results:

- `skipped` \
  The check was skipped because:
    - It is a multi check, but the hostgroup only contains one host.
    - Certain provider, architecture type, ENSA version or filesystem type are required by the check,
      but do not match the hosts.

  Skipped checks are only shown with `-s|--show-skipped`.

- `passing` \
  Everything went fine.

- `warning` \
  Something is not critical, but should checked.

- `critical`
  The check failed. The message section should explain why and the remediation section guides to a solution including links to official documentation.

  > :exclamation: It is possible, that the check failed because the supportconfig missed relevant data or the wrong provider has been chosen.
  > Check the manifest of the hosts with `tcsc hosts status GROUPNAME -d`. 

- `error` \
  An error can have multiple reasons. Here a few examples:

    - communication error with Wanda,
    - Wanda cannot process the check,
    - the check has a bug or
    - anything else.

If you get a `Wanda response: 422 - Unprocessable content.` error, in most cases it is an incompatibility between the host setup and the check. Contrary to Trento `tcsc` does not yet filters out checks, which are not suited for the support files.

Some checks are only valid on for certain providers (e.g. AWS) and do not work on others, so check fist tif the chosen provider is the correct one. 

Wanda is not very chatty in regards of error messages. If you are sure, that the check should work, something in the check or the Wanda API has changed and the checks or tools (like `rabbiteer.py`) are not up to date yet. Trento is very active. \
Try to update everything: Wanda, this project and `rabbiteer.py`. If this does not help, create an issue. 


## Troubleshooting

> :exclamation: Remember when troubleshoot, that `tcsc` is running inside a container!`

- If you experience errors after updating.  compare the personal configuration file `~/.config/tscs/config` with the new one 
  `~/.config/tscs/config.new` written by the install script. Maybe changes need to be adapted.

- If the install script - or more precise `setup/install_wanda` - terminates with:
  ```
  invalid reference format
  ```
  the provided `WANDA_URL` is wrong. The URL **must not** end with a `/`.

- If the install script - or more precise `setup/install_wanda` - terminates with:
  ```
  Error response from daemon: manifest unknown
  ```
  check if the provided `WANDA_VERSION` is correct. It can take some time until a new version turns up in the release repository.

- If `wanda status` terminates with `Wanda is not operational!` either some required container are not running or
  mandatory volumes are not present. If the container status list does not look like:
  ```
  [running]           tcsc-wanda        
  [running]           tcsc-rabbitmq     
  [exited ]           tcsc-trento-checks
  [running]           tcsc-postgres  
  ```
  try to stop and start Wanda or call `uninstall` and `install`. If the problem remains something must we wrong with the docker setup or the container images.

  > :exclamation: The tcsc-trento-checks container only provides a volume and will never run. 

 - If a `wanda status` reports 
   ```
   ... misses the mandatory volumes "tcsc-trento-checks" 
   ```
   most probably something is wrong with the tcsc-trento-checks container which provides the trento-checks
   volume containing the checks. \
   Try to stop and start Wanda or call `uninstall` and `install`. If the problem remains something must we wrong with the docker setup or the container images.

- If starting of a supportconfig container fails, the setup script preparing the container from the supportconfig failed.
  A typical error message for that would be:
  ```
  Hosts error: "Start timeout of 3s reached. tcsc-host-..." stopped running.
  ```
  Verify the host containers logs (`tcsc hosts logs CONTAINERNAME`).

- If a supportconfig container stops all by itself, the `trento-agent` died. If this happens directly after starting the container, the agent could not connect to Wanda. Check if all the Wanda containers are running and are fine (`tcsc wanda status`) and verify the host containers logs (`tcsc hosts logs CONTAINERNAME`).

- If a supportconfig container starts, but the checks do not work, check the host containers logs (`tcsc hosts logs CONTAINERNAME`).
You can enter the running host with `docker exec -it CONTAINERID bash` and run `trento-agent facts gather --gatherer GATHERER` to see if the data collection works. The  get a list of available gatherers, run `trento-agent facts list`. Documentation can be found here: https://www.trento-project.io/wanda/gatherers.html

- If all checks return the same error message or time out, but the supportconfig container is running, then most certainly something has changed in Wanda or the agent. Trento is an active project and changes happen often. Try to uninstall, update the repo and install again, which should also pull the latest image versions.

- If `tcsc wanda status` returns:
  ```
  [running]           tcsc-wanda   
  [running]           tcsc-rabbitmq
  [running]           tcsc-postgres

  Wanda is not operational!
  ```
  then most probably the communication to the container is broken. Check `wanda_url` in the configuration file.

- If you inspect the host container logs, some error messages are to be expected:
  ```
  Error initializing dbus: dial unix /run/systemd/private: connect: no such file or directory
  Error while running discovery 'cloud_discovery': exec: "dmidecode": executable file not found in $PATH
  Error while running discovery 'ha_cluster_discovery': Post "http://localhost/api/v1/collect": dial tcp 127.0.0.1:80: connect: connection refused
  Error while running discovery 'host_discovery': Post "http://localhost/api/v1/collect": dial tcp 127.0.0.1:80: connect: connection refused
  Error while running discovery 'sap_system_discovery': Post "http://localhost/api/v1/collect": dial tcp 127.0.0.1:80: connect: connection refused
  Error while running discovery 'saptune_discovery': Post "http://localhost/api/v1/collect": dial tcp 127.0.0.1:80: connect: connection refused
  Error while running discovery 'subscription_discovery': exec: "SUSEConnect": executable file not found in $PATH
  Error while sending the heartbeat to the server: Post "http://localhost/api/v1/hosts/22b5f542-91f1-5488-9664-20a8024a277e/heartbeat": dial tcp 127.0.0.1:80: connect: connection refused
  ```
  They come either from the limited container environment (the first two) or because nut a full Trento setup is present (discovery errors). \
  All of those errors can be considered as normal and do not limit the ability to execute checks.

- If checks fail, verify that the manifest has no fails. It is possible, that simply required data is not part of the   
  supportconfig. To see the manifest, run `tcsc hosts status -d GROUP`. \
  The following issues are known:

  - `usr_sap: failed`\
    The `supportutils-plugin-ha-sap` package is to old. Support was added in v1.0.5 (plugin code version).
                                
  - `saptune: failed`\
    The required JSON support is added to `plugin-saptune` with `saptune` 3.2.   


## Used Supportconfig Files

The following files from the `supportconfig` are used:

- `basic-environment.txt`\
  Content of `/etc/os-release`.\
  gatherer: `os-release`, `os-release@v1`\
  manifest entry: `os-release`

- `env.txt`\
  Output of `/sbin/sysctl -a`.\
  gatherer: `sysctl`, `sysctl@v1`\
  manifest entry: `sysctl`

- `fs-diskio.txt`\
  Content of `/etc/fstab`.\
  gatherer: `fstab`, `fstab@v1`\
  manifest entry: `fstab`

- `network.txt`\
  Content of `/etc/hosts`.\
  gatherer: `hosts`, `hosts@v1`\
  manifest entry: `hosts`

- `ha.txt`\
  Contents of:
    - `/etc/corosync/corosync.conf`
    - `/etc/sysconfig/sbd`
    - `/var/lib/pacemaker/`
  as well as the dump of `/usr/sbin/sbd -d DISK dump`.

  gatherer:
    - `corosync.conf`, `corosync.conf@v1`
    - `sbd_config`, `sbd_config@v1`
    - `cibadmin`, `cibadmin@v1`
    - `sbd_dump`, `sbd_dump@v1` 
  
  manifest entry:
    - `corosync.conf`
    - `sysconfig_sbd`
    - `pacemaker_files`
    - `sbd_dumps`

- `rpm.txt`\
  Package information for
  - `pacemaker`
  - `corosync`
  - `python3`
  - `SAPHanaSR`
  - `sbd`
  - `supportutils-plugin-ha-sap`
  - `sap_suse_cluster_connector`
  - `SLES_SAP-release`
  - `saptune`

  gatherer: `package_version`, `fstpackage_versionb@v1`\
  manifest entry: `rpm_packages`

- `systemd.txt`\
  Create empty files with the correct permissions and ownerships from:
    - `/etc/systemd/system/multi-user.target.wants/`

  gatherer: `dir_scan`, `dir_scan@v1`\
  manifest entry: `usr_sap`

- `plugin-ha_sap.txt`\
  The directory `/usr/sap/` (profiles, log files) including `/usr/sap/sapservices` as well as the outputs of
  `/usr/sap/hostctrl/exe/saphostexec` and `/usr/sap/hostctrl/exe/saphostctrl` commands.

  gatherer: 
    - `saphostctrl`, `saphostctrl@v1`
    - `sap_profiles`, `sap_profiles@v1`
    - `sapservices`, `sapservices@v1`
    - `disp+work`, `disp+work@v1`

  manifest entry:
    - `saphostctrl`
    - `usr_sap`
    - `sapservices`
    - `disp+work`
 

- `plugin-saptune.txt`\
  The following command outputs get extracted: 
    - `saptune --format json status`
    - `saptune --format json note verify`
    - `saptune --format json note list`
    - `saptune --format json solution list`
    - `saptune --format json check`
  gatherer: `saptune`, `saptune@v1`\
  manifest entry: `saptune`


> :exclamation: Not all files can or data can be present in a supportconfig. Reasons can be:
>   - the files were skipped deliberately when the supportconfig was created,
>   - the data was never on the system
>   - the data gets collected in newer versions of the supportconfig
>   - the used plugin was not present (missing package) or the version does not yet contain the needed data

## How does the Trento agent get the supportconfig data?

The `tcsc hosts create` command starts a host container for each given supportconfig. The supportconfig is mounted at `/SUPPORTCONFIG` either as directory (e.g. `/scc_vmhdbqas02_250107_1541`) or as archive (e.g. `scc_vmhdbqas02_250107_1541.txz`), depending on how it was passed at the command line. 
The processings scripts in `/sc` (copied into the image at build) do the processing. At container start `/sc/startup` gets executed. First it runs `sc/process_supportfiles` to process the support files and finally starts the trento agent.

The `sc/process_supportfiles` script extracts the supportconfig in case of an archive and calls `split-supportconfig` ([https://github.com/SUSE/supportconfig-utils](https://github.com/SUSE/supportconfig-utils)) to create individual files from selected supportconfig text files in `/rootfs`. Only files or directories required by the Trento gatherers are copied from `/rootfs` into `/` in the next step.  

Most commanda called by gatherers exist as mocks feeded with supportconfig data and mimick the real command (limited to the functionality required by the gatherers). These mock commands are also located in `/sc` and get copied into the root filesystem. Examples for those mock commands are: `cibadmin`, `sbd`, `saptune`, `disp+work` and `sysctl`.

For the `package_version` gatherer dummy RPM packages are generated and installed out of `rpm.txt` for checked packages.

## Which Gatherer Works

For a check to work, the called gatherer must work with the confinements of the container. basically we have two hurdles:

1. The data must part of the supportconfig or the project must be extended to consume more input data.
2. The gatherer must retrieve the data in the ways the programmer has intended it. 

This chapter contains an evaluation for the gatherers (December 2024).

### Working

#### `cibadmin`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/cibadmin.go \
**Chances: :smiley:**

Works by providing a script as `cibadmin` command, which returns `/var/lib/pacemaker/cib/cib.xml` (`ha.txt`) when called with `--query --local`.

#### `corosync.conf`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/corosyncconf.go \
**Chances: :smiley:**

Works by providing `/etc/corosync./corosync.conf` (`ha.txt`) in the container rootfs.

#### `dir_scan`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/dir_scan.go \
**Chances: :neutral_face:**

The gatherer scans directories with a glob pattern provided as argument and returns a list of files matched by the pattern with group/user information associated to each file. Only such checks would work, which address directories/files provided by the supportconfig. **It depends therefore on the check if it works or not.**

#### `fstab`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/fstab.go \
**Chances: :smiley:**

Works by providing `/etc/fstab` (`fs-diskio.txt`) in the container rootfs.

#### `hosts`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/hostsfile.go \
**Chances: :smiley:**

Works by providing `/etc/hosts` (`network.txt`) in the container rootfs.

#### `os-release`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/osrelease.go \
**Chances: :smiley:**

Works by providing `/etc/os-release` (`basic-environment.txt`) in the container rootfs.

#### `package_version`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/packageversion.go \
**Chances: :smiley:**

Works by providing an empty on-the-fly created RPM package from `rpm.txt`.

#### `sap_profiles`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapprofiles.go \
**Chances: :smiley:**

Returns content of `/sapmnt/<SID>/profile` and instance profiles are part of `plugin-ha_sap.txt`.

#### `sapservices`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapservices.go \
**Chances: :smiley:**

The `/usr/sap/sapservices` is part of `plugin-ha_sap.txt`.

#### `sbd_config`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sbd.go \
**Chances: :smiley:**

Works by providing `/etc/sysconfig/sbd` (`ha.txt`) in the container rootfs.

#### `sbd_dump`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sbddump.go \
**Chances: :smiley:**

Works by having a `sbd` script which returns the expected output from `sbd -d <device> dump` by processing the sbd dumps of `ha.txt`.

#### `sysctl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sysctl.go \
**Chances: :smiley:**

The gatherer executes `sysctl -a` which is part of the supportconfig. Just a script named `sysctl` is needed which returns that part of `env.txt`.

#### `saptune`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/saptune.go \
**Chances: :neutral_face:/:smiley:**

Calls `saptune --format json` command with limited set of commands. The `plugin-saptune.txt` for 3.2 will contain the JSON output. 

#### `systemd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/systemd_v2.go \
**Chances: :neutral_face:**

The gatherer connects to `dbus` to communicate with `systemd`. For checks to work, the container needs a `dbus` and a fake `systemd` answering the questions of the gatherer from the supportconfig.


### Not Working

#### `corosync-cmapctl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/corosynccmapctl.go \
**Chances: :rage:**

The gatherer is calling `corosync-cmapctl -b`, which therefore must work. With the corosync object database being an in-memory non-persistent database, checks using that gatherer won't work as long as a dump of the corosync object database is not part of the supportconfig (or provided otherwise).

#### `disp+work`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/dispwork.go \
**Chances: :rage:**

With calling the `disp+work` command to get compilation_mode, kernel_release and patch_number checks do not work. This data is not part of the supportconfig. To get it to work additional information must be provided as well as a `disp+work` replacement, which presents the data in the same way as the original `disp+work`.

#### `groups`
https://www.trento-project.io/wanda/gatherers.html#groupsv1 \
**Chances: :rage:**

With `/etc/groups` not part of the supportconfig, checks using this gatherer do not work.

#### `mount_info` 
https://www.trento-project.io/wanda/gatherers.html#groupsv1 \
**Chances: :rage:**

The gatherer does not work most probably. It relies on https://github.com/moby/sys/tree/main/mountinfo to get the mount information. It has to be checked how the project is doing it, but if it accesses `/proc` it can become difficult to provide the supportconfig data. 

Also `blkid DEVICE -o export` gets called by the gatherer. The original command must be replaced by a script presenting the output of `blkid` (`fs-diskio.txt`) in the way the gatherer expects it.

#### `passwd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/passwd.go \
**Chances: :rage:**

With `/etc/passwd` not part of the supportconfig, checks using this gatherer does not work.

#### `products`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/products.go \
**Chances: :rage:**

With only the file list of `/etc/products.d/` but not the content of those files being part of the supportconfig, checks using this gatherer do not work.

#### `sapcontrol`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapcontrol.go \
**Chances: :rage:**

This is a complex gatherer and from reading the description it uses a unix socket connection with `/tmp/.sapstream5xx13`.
Besides the fact, that those data might not be part of the supportconfig, this approach would require to write a program that present the data via a socket to the gatherer.

#### `saphostctrl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/saphostctrl.go \
**Chances: :rage:**

Executes `/usr/sap/hostctrl/exe/saphostctrl -function FUNCTION`. Currently only `Ping` and `ListInstances` seems to be supported. \
`ListInstances` is part of `plugin-ha_sap.txt`, but `Ping` is still missing but might be added in the future.

#### `sapinstance_hostname_resolver`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapinstancehostnameresolver.go \
**Chances: :rage:**

Th gatherer needs to be investigated further, but the required data is not part of the supportconfig.

#### `verify_passwd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/verifypassword.go \
**Chances: :rage:**

The command `getent shadow USER` must work. Since the supportconfig does not contain `/etc/shadow` or a dump of the user`s password hashes, checks using this gatherer does not work.

#### `ascsers_cluster`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/ascsers_cluster.go \
**Chances: :rage:**

At first glance the gatherer requires `sapcontrol` to work and SAP directories to be present. Most probably not working yet.


# Configuration File

The configuration file in JSON is located at `~/.config/tcsc/config` anf is generated by the `install` script. 

| Parameter | Type   | Default | Meaning
|---------- | ----   | ------- | -------
| `id`      | string | -       | Unique ID to identify individual `tcsc` installations. The id is used to label (`com.suse.tcsc.uid`) supportconfig containers
| `wanda_containers` | list | `["tcsc-rabbitmq", "tcsc-postgres", "tcsc-wanda", "tcsc-trento-checks"]` | List of the names of the Wanda containers.
| `wanda_label` | string | `"com.suse.tcsc.stack=wanda"` | Label for all Wanda containers.
| `hosts_label` | string | `"com.suse.tcsc.stack=host"` | Label for all host containers.
| `docker_timeout` | int | `10` | Timeout in seconds for `docker` operations.
| `startup_timeout` | int | `3` | Timeout in seconds until a host container start is considered failed.
| `wanda_url` | string | `"http://tcsc-wanda:4000"` | URL to the Wanda stack (from inside the `tcsc` container).
| `hosts_image` | string | `"ghcr.io/scmschmidt/tcsc_host"` | Image for the host containers.
| `wanda_autostart` | bool | `true` | Enables/disables starting of Wanda on demand.
| `colored_output`" | bool | `true` | Enables/disables coloring the output.

> :bulb: Should you build local host images, check and adapt `hosts_image`. \
> The scripts `setup/install_cmd` and `setup/install_cmd_local` set the parameter to `ghcr.io/scmschmidt/tcsc_host`. \
> The script `setup/install_hosts` sets it to `ghcr.io/scmschmidt/tcsc_host` and `setup/install_hosts_local` to `tscs_host`.

```
{
    "id": "73f31f16-eaba-11ee-994d-5b663d913758",
    "wanda_containers": [
        "tcsc-rabbitmq",
        "tcsc-postgres",
        "tcsc-wanda",
        "tcsc-trento-checks"
    ],
    "wanda_label": "com.suse.tcsc.stack=wanda",
    "hosts_label": "com.suse.tcsc.stack=host",
    "docker_timeout": 10,
    "startup_timeout": 3,
    "wanda_url": "http://tcsc-wanda:4000",
    "hosts_image": "tscs_host",
    "wanda_autostart": true,
    "colored_output": true
}
```

# JSON Support

For using `tcsc` in scripts or integrate it into automation, `-j` switches to JSON output only for all commands.