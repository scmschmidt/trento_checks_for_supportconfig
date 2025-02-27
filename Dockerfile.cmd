#FROM python:3.14.0a2-slim-bookworm
FROM python:3-slim

LABEL com.suse.tcsc.stack="cmd"

# Copy the tcsc Python files and rabbiteer into the image.
COPY src/* /

# Install requirements.
RUN pip3 install docker termcolor defusedxml

# Install dbus-uuidgen and uuidgen.
RUN apt-get update 
RUN apt-get -y install dbus-bin uuid-runtime

ENTRYPOINT [ "./tcsc.py" ]
#CMD [ "/bin/bash", "-c", "./tcsc.py ${ARGS}" ]