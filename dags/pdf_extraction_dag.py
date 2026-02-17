from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from process_pdf import process_pdf

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'pdf_extraction',
    default_args=default_args,
    description='Extract PDF content and store in database',
    schedule_interval=None,
    catchup=False,
)

def extract_pdf_task(**context):
    pdf_path = context['dag_run'].conf.get('pdf_path')
    if not pdf_path:
        raise ValueError("pdf_path must be provided in DAG run configuration")
    return process_pdf(pdf_path)

extract_task = PythonOperator(
    task_id='extract_and_store_pdf',
    python_callable=extract_pdf_task,
    dag=dag,
)
