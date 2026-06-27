"""
Airflow DAG — daily RSS ingestion.

Schedule: 06:00 UTC every day (before the working day in EU/US).

To deploy:
  1. Copy (or symlink) this file into your Airflow DAGs folder.
  2. Set AIRFLOW_CONN_MAI_NEWS_DB or DATABASE_URL in the Airflow
     environment / Connections UI.
  3. Ensure the worker has data_engineering/ on PYTHONPATH and the
     packages from data_engineering/requirements.txt installed.

The DAG is intentionally minimal: one PythonOperator that calls
pipeline.run().  Add sensors, alerting, or retries here as needed.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Make data_engineering/ importable when Airflow runs from the dags/ folder.
_DE_ROOT = Path(__file__).parent.parent
if str(_DE_ROOT) not in sys.path:
    sys.path.insert(0, str(_DE_ROOT))

from airflow import DAG
from airflow.operators.python import PythonOperator


def _run_ingestion(**context) -> None:
    """Callable for PythonOperator.  Logs result to XCom."""
    import pipeline
    result = pipeline.run()
    print(f"[ingest_dag] result: {result}")
    context["ti"].xcom_push(key="ingest_result", value=result)


with DAG(
    dag_id="mai_news_ingest",
    description="Daily RSS ingestion — fetch, embed, upsert to pgvector",
    schedule="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "owner": "data-engineering",
    },
    tags=["mai-news", "ingestion"],
) as dag:

    ingest = PythonOperator(
        task_id="run_ingest_pipeline",
        python_callable=_run_ingestion,
    )
