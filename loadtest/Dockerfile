FROM python:3.12-slim
WORKDIR /loadtest
RUN pip install --no-cache-dir locust==2.32.10
COPY loadtest/locustfile.py /loadtest/locustfile.py
ENTRYPOINT ["locust", "-f", "/loadtest/locustfile.py"]
