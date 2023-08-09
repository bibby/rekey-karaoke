FROM python:3

RUN \
  echo "deb https://deb.nodesource.com/node_20.x bullseye main" > /etc/apt/sources.list.d/nodesource.list && \
  wget -qO- https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add - && \
  apt-get update && \
  apt-get upgrade -yqq && \
  apt-get install -yqq nodejs && \
  pip install -U pip && \
  apt-get install -y ffmpeg && \
  rm -rf /var/lib/apt/lists/*


COPY requirements.txt /tmp/reqs.txt
RUN pip install -r /tmp/reqs.txt

COPY . /opt/src/server
WORKDIR /opt/src/server

RUN npm install
RUN npm run tailwind

EXPOSE 1337

RUN ln -sf /dev/stdout /var/log/app.log \
    && ln -sf /dev/stderr /var/log/error.log

ENTRYPOINT ./start.sh
