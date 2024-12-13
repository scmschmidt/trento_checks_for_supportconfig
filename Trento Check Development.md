# Trento Check Development

The project can assist Trento check development by:

    - managing Wanda,
    - allowing testing of checks by simulating (cluster) hosts and
    - execute the checks.

## Install, Update and Uninstall

Call the install script with the environment variable `CHECK_DIR` pointing to your check file directory:
```
CHECK_DIR=/tmp/checks ./install
```

> :bulb: If you already have a `tcsc` installation, simply call `CHECK_DIR=/tmp/checks setup/install_wanda` to 
> re-create the Wanda container.

Uninstall works exactly as described in the [README](README.md#removal). 

An update works exactly as described in the [README](README.md#update), but don't forget to set `CHECK_DIR`.

## Managing Wanda

This is exactly the same as described in the [README](README.md#manage-wanda)

## Using Host Containers

To use the host containers to test the checks, the gatherer must be supported, meaning the required information is present in the support files.

Unpack the development supportconfigs (TBD) and start the host container as described in the [README](README.md#manage-hosts-supportconfig-containers)

To test your check alter the files in those directories and use `tcsc hosts rescan GROUPNAME` to reread the altered files.
Execute the check.


#TODO: - Prepare a supportconfigs (cluster) limited to the supported file as base


## Executing Checks

This is exactly the same as described in the [README](README.md#run-the-checks)