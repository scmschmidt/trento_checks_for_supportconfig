# Content of `setup/`

The directory contains install, uninstall and build scripts mostly called by `install` and `unistall`.

- called by `install`
    - `install_wanda`\
       Pulls the Wanda images from the chosen registry, starts the container and checks the availability of Wanda.
    - `install_host` (only if `BUILD_LOCAL` is set)\
       Pulls the host image from the GitHub container registry.
    - `install_cmd` (only if `BUILD_LOCAL` is set)\
       Pulls the command image from the GitHub container registry and creates the tcsc config file.
    - `install_host_local` (only if `BUILD_LOCAL` is unset/empty)\
       Builds the host image from `Dockerfile.host`.
    - `install_cmd_local` (only if `BUILD_LOCAL` is unset/empty)\
       Builds the command image from `Dockerfile.cmd` and creates the tcsc config file.

- called by `uninstall`
    - `uninstall_wanda`\
      Removes all Wanda containers, images and volumes.
    - `uninstall_host`\
      Removes all host containers, images and volumes.
    - `uninstall_cmd`\
      Removes all command containers, images and volumes.
    - `uninstall_networks`\
      Removes the tcsc default network.

- `build_publish_ghcr_host`\
   Logs into the GitHub container registry (token file must be provided), build the host image and uploads it.

- `build_publish_ghcr_cmd`\
   Logs into the GitHub container registry (token file must be provided), build the command image and uploads it.

