# Architecture

This document describes the architecture of the project and goes into detail of some concepts.

## Used Containers

TODO: ADD DIAGRAM HERE (Including images, volumes and networks)


## Labeling an Naming Concept

> :bulb: `tcsc` does not track started, stopped or removed containers, but relies on the correct labeling of docker objects, like container.


The following labels are used:

- `com.suse.tcsc.stack`\
  Each container and the host image handled by this project has this label.
  Wanda objects have the value `wanda` and host objects the value `host`

- `com.suse.tcsc.hostgroup`\
  This label exists only for host objects and has the hostgroup name given by the user as value.

- `com.suse.tcsc.uuid`\
  This label exists only for host objects and contains the UUID of the `tcsc` installation.

- `com.suse.tcsc.supportfiles`\
  This label exists only for host objects and contains a list of the associated support files.

- `com.suse.tcsc.supportconfig`\
  This label exists only for host objects and contains the filename of the associated supportconfig (suffixes removed).

- `com.suse.tcsc.agent_id`\
  This label exists only for host objects and contains the `trento-agent` id for that host.

- `com.suse.tcsc.expected_state`\
  This label defines the expected container state for an operational Wanda.

- `com.suse.tcsc.expected_volumes`\
  This optional label contains a comma-separated list of required volume names. The volume must
  be prefixed with the project name `tcsc` separated by an underscore.

All container names start with the prefix `tcsc-`. For the three Wanda containers the names are:

  - `tcsc-rabbitmq`
  - `tcsc-postgres`
  - `tcsc-wanda`
  - `tcsc-trento-checks`

For host container names the prefix is followed by the string `host`, the hostgroup name and a random string of 8 characters separated by a dash:
`tcsc-host-<HOSTGROUP>-<UUID>`

For Wanda, the `docker-compose-wanda.yaml` sets the correct labels and names.

> Example:
>
> Assumed the `tcsc` UUID is *691f589c-da35-11ee-994d-2df1b03e5ad0* and the user has two host groups *ACMEprod_1* and *ACMEprod_2* which two hosts each, the naming and labeling would be:
>
> Wanda:
> 
>  - tcsc-rabbitmq
>     - com.suse.tcsc.stack=wanda
>  - tcsc-postgres
>     - com.suse.tcsc.stack=wanda
>  - tcsc-wanda
>     - com.suse.tcsc.stack=wanda
>  - tcsc-trento-checks
>     - com.suse.tcsc.stack=wanda
>
> Hosts:
>
>  - tcsc-host-ACMEprod_1-eo3fbp4w
>     - com.suse.tcsc.stack=host
>     - com.suse.tcsc.hostgroup=ACMEprod_1
>     - com.suse.tcsc.supportfiles=[scc_hdbprda1_231011_1528.txz]
>     - com.suse.tcsc.supportconfig=scc_hdbprda1_231011_1528
>     - com.suse.tcsc.uuid=691f589c-da35-11ee-994d-2df1b03e5ad0
>     - com.suse.tcsc.agent_id=ddefc515-f5ce-587c-9953-cb1ab65bb278
>
>  - tcsc-host-ACMEprod_1-qvmscofr
>     - com.suse.tcsc.stack=host
>     - com.suse.tcsc.hostgroup=ACMEprod_1
>     - com.suse.tcsc.supportfiles=[scc_hdbprda2_231011_1533.txz]
>     - com.suse.tcsc.supportconfig=scc_hdbprda2_231011_1533
>     - com.suse.tcsc.uuid=691f589c-da35-11ee-994d-2df1b03e5ad0
>     - com.suse.tcsc.agent_id=3b2bcdd3-f79b-5796-b0c8-aab9e9f39a2b
>
>  - tcsc-host-ACMEprod_2-bcakg5vz
>     - com.suse.tcsc.stack=host
>     - com.suse.tcsc.hostgroup=ACMEprod_2
>     - com.suse.tcsc.supportfiles=[scc_hdbprdb1_231011_1643.txz]
>     - com.suse.tcsc.supportconfig=scc_hdbprdb1_231011_1643
>     - com.suse.tcsc.uuid=691f589c-da35-11ee-994d-2df1b03e5ad0
>     - com.suse.tcsc.agent_id=aa18c008-f806-5c5e-9d1a-a05e93c344b6
>
>  - tcsc-host-ACMEprod_2-eaf7dyjt
>     - com.suse.tcsc.supportfiles=[scc_hdbprdb2_231011_1658.txz]
>     - com.suse.tcsc.supportconfig=scc_hdbprdb2_231011_1658
>     - com.suse.tcsc.stack=host
>     - com.suse.tcsc.hostgroup=ACMEprod_2
>     - com.suse.tcsc.uuid=691f589c-da35-11ee-994d-2df1b03e5ad0
>     - com.suse.tcsc.agent_id=dd1b61be-ad6c-559d-9f10-27a45f9fc4a5
