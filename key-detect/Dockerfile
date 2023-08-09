FROM python:3
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY index.py /usr/local/bin/key-detect

ENTRYPOINT ["/usr/local/bin/key-detect"]
