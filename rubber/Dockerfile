FROM debian:sid
RUN apt-get update && apt-get install -y rubberband-cli rubberband-ladspa rubberband-lv2

COPY rubber.sh /usr/local/bin/rubber
ENTRYPOINT ["/usr/local/bin/rubber"]
