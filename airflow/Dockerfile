FROM apache/airflow:2.10.5-python3.12
COPY customer_portal/requirements.txt /tmp/customer-requirements.txt
RUN sed '/^numpy[<=>]/d' /tmp/customer-requirements.txt > /tmp/airflow-requirements.txt \
    && pip install --no-cache-dir -r /tmp/airflow-requirements.txt psycopg2-binary "numpy<2"
COPY airflow/dags /opt/airflow/dags
