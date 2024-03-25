FROM opensuse/leap:15.4

LABEL com.suse.tcsc.stack="host"

# Add Trento development repo
RUN zypper ar -G https://download.opensuse.org/repositories/devel:/sap:/trento:/factory/15.4/ trento-devel

# Install needed packages.
RUN zypper --non-interactive in trento-agent ruby tar xz python3 sudo rpm-build rpmdevtools

# Install optional packages (for debugging)
RUN zypper --non-interactive in vim iproute2 netcat-openbsd iputils less

# Get supportconfig split script.
ADD https://raw.githubusercontent.com/SUSE/supportconfig-utils/master/bin/split-supportconfig /split-supportconfig
RUN chmod +x /split-supportconfig


