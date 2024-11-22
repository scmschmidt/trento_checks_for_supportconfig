# tcsc - Trento checks for supportconfig

Makes Trento checks usable for support cases by using them on supportconfigs. Also `jq` is needed by the scripts to parse JSON.

> :bulb: This is a rewrite of the proof-of-value which final version can be found here: https://github.com/scmschmidt/trento_checks_for_supportconfig/releases/tag/pov-final

## Prerequisites

You need `git` (optional) as well as `docker` and `docker-compose` installed to run containers.

> :bulb: The `tcsc.py` is a Python script which is containerized by default. You can run it locally with a current Python version (3.11 has been tested), but you need to adapt `wanda_url` to "http://localhost:4000" in the configuration file (see [Configuration File](#configuration-file)) or prvide your own config with `-c`.


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

Do the following steps as normale user:

1. Clone this repo and enter the project directory (or get it otherwise): 

   ```
   git clone https://github.com/scmschmidt/trento_checks_for_supportconfig.git
   cd trento_checks_for_supportconfig
   ```

1. Run: `./install` 

   It sets up and starts the Wanda containers as well as creating the image for the supportconfig hosts. 

   > :bulb: You can influence the used Wanda version by setting the environment variable `WANDA_VERSION`.
   > The repo always uses the latest released version. To use a specific one, run: `WANDA_VERSION=... ./install`

   > :exclamation: If the install fails when building the images, run it again. Sometimes after a second or third run the pull completes. 

1. Place the script `tcsc` in `~/bin` or `/usr/local/bin` (last requires root).


## Update

To update the installation:

  1. Enter the repo directory.
  1. Update the repo: `git pull`
  1. Delete the existing setup: `./uninstall`
  1. Install the updated version: `./install`

> :warning: An uninstallation stops and removes the `tcsc` container, the Wanda container as well as all supportconfig containers.

> :exclamation: After a `git pull` do not forget to update the `tcsc` script in `~/bin`, `/usr/local/bin` or wherever you put it. 


## Removal

To remove all containers, images, volumes and networks, call: `./uninstall` and delete the `tcsc` script in `~/bin`, `/usr/local/bin` or wherever you put it. 


## Inspect a supportconfig

The tool to work with, is `tcsc`. It can

  - manage the Wanda stack,
  - manage the required supportconfig containers
  - list amd execute the checks.


### Manage Wanda

To inspect a supportconfig, the Wanda stack must be running. To verify the status, run:
```
tcsc wanda status
```

> :bulb: Per default `tcsc` starts Wanda automatically if needed. 
> This can be changed by setting `wanda_autostart` in `~/.config/tcsc/config`. 
> See [Configuration File](#configuration-file) for details.

In case Wanda is not there, run:
```
tcsc wanda start
``` 

If you do not need Wanda anymore, you can stop the stack with:
```
tcsc wanda stop
``` 

### Manage Hosts (supportconfig Containers)

To run checks, for each supportconfig an individual (host) container must be started. Such a container runs the `trento-agent` inside and connects to Wanda. To Wanda the container is simply a host which shall be checked. Therefore the content of the supportconfig as well as all the additional support files are placed inside the container in a way, that the `trento-agent` accepts it as system data. \
The idea is to "simulate" the customers setup using the support files and let Wanda check it.

Currently there are two types of Trento checks. Single checks and multi checks. \
Single checks run only on one individual host, contrary multi checks which need at least two systems (depending on the check of cause) and it most cases compare settings between them.

As consequence you should always start one container for each host with the appropriate support files if you deal with a cluster. 

To start a host container, run:
```
tcsc hosts start GROUPNAME FILE...
```

- `GROUPNAME` is a free name to group hosts which belong together (e.g. cluster). This name is later used to execute checks on the correct hosts. Use case numbers, system names, customer names, whatever is semantic.

- `FILE` is the support file you wish to be incorporated. \
   **Currently only supportconfigs are supported.** In the future, hb_reports, SAP sysinfo reports or SAP trace files can be used too.

If you do not need the host container anymore stop and destroy them with:
```
tcsc hosts stop GROUPNAME
```
and
```
tcsc hosts remove GROUPNAME
```

> :bulb: A `stop` only stops the container, but leaves the images, so they can be started later again simply with: `tcsc hosts start GROUPNAME`. The support files will not read again.

> :wrench: Example for a HA cluster:
> ```
> tcsc hosts start ACME-HANAProd cases/47114711/scc_vmhana01_231011_1528.txz
> tcsc hosts start ACME-HANAProd cases/47114711/scc_vmhana02_231011_1533.txz
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

> :bulb: Use `-d` or `--detail` to get more information about the host containers, like the container id, the Trento agent id, the hostname (from the supportconfig), the hostgroup and the referenced support files (with the container hostfs mountpoint).

If a previously started container is not listed, see section [Troubleshooting](#Troubleshooting) below.


### Run the Checks

To get an overview about existing checks, run:

```
tcsc checks list
```
It lists all checks grouped by the Trento check group and tells if `tcsc` currently supports it:

 - `supported` \
   The check is supported.

 - `not supported` \
   The check is not (yet) supported, because the information required is not part of
   the support files or there is not yet a method implemented to prepare the data
   for the Trento gatherers (see [Which Gatherer Works](#which-gatherer-works) for details).

 - `unknown` \
   The check (or more precise the used gatherer) is not known to `tcsc` yet.

> :bulb: Use `-d` or `--detail` to get more information about the checks, like type, supported providers and cluster types or the used gatherer.


After all your host containers have been started, you can execute the supported checks:

```
tcsc checks GROUPNAME -p PROVIDER
```

- `GROUPNAME` identifies the host containers where the checks should be executed.

- `PROVIDER` defines the infrastructure of the hosts the support files are coming from.
  Depending on the infrastructure some checks use different settings or may not. \
  Either `default`, `kvm`, `vmware`, `azure` or `gcp`.

  > :exclamation: Currently you have to provide the correct provider yourself. Future versions get an auto-detection.

If only a limited amount of checks shall be executed, you can either provide Trento check groups:
```
tcsc checks GROUPNAME -p PROVIDER -g GROUP...
```
or the check ids itself:
```
tcsc checks GROUPNAME -p PROVIDER -c CHECK
```
  
- `GROUP` allows to select a subset of checks depending on their group.
- `CHECK` allows you to select a specific check. 

> :wrench: To have more then one group or check, use `-g` or `-c` multiple times.

> :wrench: To see only checks, which have not passed, add the option `-f`.

A check can have the following results:

- `passing` \
  Everything went fine.

- `warning` \
  Something is not critical, but should checked.

- `critical`
  The check failed. The message section should explain why and the remediation section guides to a solution including links to official documentation.

  > :exclamation: It is possible, that the check failed because the supportconfig missed relevant data or the wrong provider has been chosen. 

- `error` \
  An error can have multiple reasons. Here a few examples:

    - communication error with Wanda
    - Wanda cannot process the check
    - the check has a bug
    - anything else.

If you get a `Wanda response: 422 - Unprocessable content.` error, in most cases it is an incompatibility between the host setup and the check. Contrary to Trento `tcsc` does not yet filters out checks, which are not suited for the support files.

Some checks are only valid on for certain providers (e.g. AWS) and do not work on others, so check fist tif the chosen provider is the correct one. 

Wanda is not very chatty in regards of error messages. If you are sure, that the check should work, something in the check or the Wanda API has changed and the checks or tools (like `rabbiteer.py`) are not up to date yet. Trento is very active. \
Try to update everything: Wanda, this project and `rabbiteer.py`. If this does not help, create an issue. 


## The Image for the supportconfig Containers

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


## Troubleshooting

> :exclamation: Remember when troubleshoot, that `tcsc` is running inside a container!`

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


## Which Gatherer Works

For a check to work, the called gatherer must work with the confinements of the container. basically we have two hurdles:

1. The data must part of the supportconfig or the project must be extended to consume more input data.
2. The gatherer must retrieve the data in the ways the programmer has intended it. 

This chapter contains an evaluation for the gatherers (November 2024).

### `cibadmin`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/cibadmin.go \
**Chances: :smiley:**

Works by providing a script as `cibadmin` command, which returns `/var/lib/pacemaker/cib/cib.xml` (`ha.txt`) when called with `--query --local`.

### `corosync.conf`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/corosyncconf.go \
**Chances: :smiley:**

Works by providing `/etc/corosync./corosync.conf` (`ha.txt`) in the container rootfs.

### `corosync-cmapctl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/corosynccmapctl.go \
**Chances: :rage:**

The gatherer is calling `corosync-cmapctl -b`, which therefore must work. With the corosync object database being an in-memory non-persistent database, checks using that gatherer won't work as long as a dump of the corosync object database is not part of the supportconfig (or provided otherwise).

### `dir_scan`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/dir_scan.go \
**Chances: :neutral_face:**

The gatherer scans directories with a glob pattern provided as argument and returns a list of files matched by the pattern with group/user information associated to each file. Only such checks would work, which address directories/files provided by the supportconfig. **It depends therefore on the check if it works or not.**

### `disp+work`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/dispwork.go \
**Chances: :rage:**

With calling the `disp+work` command to get compilation_mode, kernel_release and patch_number checks do not work. This data is not part of the supportconfig. To get it to work additional information must be provided as well as a `disp+work` replacement, which presents the data in the same way as the original `disp+work`.

### `fstab`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/fstab.go \
**Chances: :smiley:**

Works by providing `/etc/fstab` (`fs-diskio.txt`) in the container rootfs.

### `groups`
https://www.trento-project.io/wanda/gatherers.html#groupsv1 \
**Chances: :rage:**

With `/etc/groups` not part of the supportconfig, checks using this gatherer do not work.

### `hosts`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/hostsfile.go \
**Chances: :smiley:**

Works by providing `/etc/hosts` (`env.txt`) in the container rootfs.

### `mount_info` 
https://www.trento-project.io/wanda/gatherers.html#groupsv1 \
**Chances: :rage:**

The gatherer does not work most probably. It relies on https://github.com/moby/sys/tree/main/mountinfo to get the mount information. It has to be checked how the project is doing it, but if it accesses `/proc` it can become difficult to provide the supportconfig data. 

Also `blkid DEVICE -o export` gets called by the gatherer. The original command must be replaced by a script presenting the output of `blkid` (`fs-diskio.txt`) in the way the gatherer expects it.

### `os-release`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/osrelease.go \
**Chances: :smiley:**

Works by providing `/etc/os-release` (`basic-environment.txt`) in the container rootfs.

### `package_version`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/packageversion.go \
**Chances: :smiley:**

Works by providing an empty on-the-fly created RPM package from `rpm.txt`.

### `passwd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/passwd.go \
**Chances: :rage:**

With `/etc/passwd` not part of the supportconfig, checks using this gatherer does not work.

### `products`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/products.go \
**Chances: :rage:**

With only the file list of `/etc/products.d/` but not the content of those files being part of the supportconfig, checks using this gatherer do not work.

### `sapcontrol`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapcontrol.go \
**Chances: :rage:**

This is a complex gatherer and from reading the description it uses a unix socket connection with `/tmp/.sapstream5xx13`.
Besides the fact, that those data is not part of the supportconfig, this approach would require to write a program that present the data via a socket to the gatherer.

### `saphostctrl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/saphostctrl.go \
**Chances: :rage:**

Executes `/usr/sap/hostctrl/exe/saphostctrl -function FUNCTION`. Regardless which functions are supported, the data is not part of the supportconfig. For checks to work the required data/dumps must be provided by other means.

### `sap_profiles`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapprofiles.go \
**Chances: :rage:**

Returns content of `/sapmnt/<SID>/profile` which is not part of the supportconfig.

### `sapinstance_hostname_resolver`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapinstancehostnameresolver.go \
**Chances: :rage:**

Th gatherer needs to be investigated further, but the required data is not part of the supportconfig.

### `sapservices`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sapservices.go \
**Chances: :rage:**

Presents `/usr/sap/sapservices` which is not part of the supportconfig.

### `saptune`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/saptune.go \
**Chances: :neutral_face:**

Calls `saptune` command with limited set of commands. It should be possible to provide a script which returns the information extracted from files of `plugin-saptune.txt`.

### `sbd_config`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sbd.go \
**Chances: :smiley:**

Works by providing `/etc/sysconfig/sbd` (`ha.txt`) in the container rootfs.

### `sbd_dump`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sbddump.go \
**Chances: :smiley:**

Works by having a `sbd` script which returns the expected output from `sbd -d <device> dump` by processing the sbd dumps of `ha.txt`.

### `sysctl`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/sysctl.go \
**Chances: :smiley:**

The gatherer executes `sysctl -a` which is part of the supportconfig. Just a script named `sysctl` is needed which returns that part of `env.txt`.

### `systemd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/systemd_v2.go \
**Chances: :neutral_face:**

The gatherer connects to `dbus` to communicate with `systemd`. For checks to work, the container needs a `dbus` and a fake `systemd` answering the questions of the gatherer from the supportconfig.

### `verify_passwd`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/verifypassword.go \
**Chances: :rage:**

The command `getent shadow USER` must work. Since the supportconfig does not contain `/etc/shadow` or a dump of the user`s password hashes, checks using this gatherer will not work.

### `ascsers_cluster`
https://github.com/trento-project/agent/blob/main/internal/factsengine/gatherers/ascsers_cluster.go \
**Chances: :question:**

Need to ba analyzed.


# Configuration File

The configuration file in JSON is located at `~/.config/tcsc/config` anf is generated by the `install` script. 

| Parameter | Type   | Default | Meaning
|---------- | ----   | ------- | -------
| `id`      | string | -       | Unique ID to identify individual `tcsc` installations. The id is used to label (`com.suse.tcsc.uid`) supportconfig containers
| `wanda_containers` | list | `["tcsc-rabbitmq", "tcsc-postgres", "tcsc-wanda"]` | List of the names of the Wanda containers.
| `wanda_label` | string | `"com.suse.tcsc.stack=wanda"` | Label for all Wanda containers.
| `hosts_label` | string | `"com.suse.tcsc.stack=host"` | Label for all host containers.
| `docker_timeout` | int | `10` | Timeout in seconds for `docker` operations.
| `startup_timeout` | int | `3` | Timeout in seconds until a host container start is considered failed.
| `wanda_url` | string | `"http://tcsc-wanda:4000"` | URL to the Wanda stack (from inside the `tcsc` container).
| `hosts_image` | string | `"tscs_host"` | Image for the host containers.
| `wanda_autostart` | bool | `true` | Enables/disables starting of Wanda on demand.
| `colored_output`" | bool | `true` | Enables/disables coloring the output.

```
{
    "id": "73f31f16-eaba-11ee-994d-5b663d913758",
    "wanda_containers": [
        "tcsc-rabbitmq",
        "tcsc-postgres",
        "tcsc-wanda"
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