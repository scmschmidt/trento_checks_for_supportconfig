#FROM registry.suse.com/bci/bci-base:latest
FROM opensuse/leap:latest

# Install needed packages.
RUN zypper --non-interactive in trento-agent ruby tar xz python3 sudo

# Install optional packages (for debugging)
RUN zypper --non-interactive in vim iproute2 netcat-openbsd iputils   

# Get supportconfig split script.
ADD https://raw.githubusercontent.com/SUSE/supportconfig-utils/master/bin/split-supportconfig /split-supportconfig
RUN chmod +x /split-supportconfig


