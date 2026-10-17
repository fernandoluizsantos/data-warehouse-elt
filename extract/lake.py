"""Camada raw do data lake (S3 compatível): grava e lê lotes sem alterar o dado."""
import json
from datetime import datetime

import boto3
from botocore.config import Config

from extract.config import Settings


def s3_client(settings: Settings):
    # endpoint_url=None -> AWS de verdade; com valor -> SeaweedFS/MinIO local
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        config=Config(s3={"addressing_style": "path"}),
    )


def batch_key(entity: str, extracted_at: datetime, run_id: str, batch_number: int) -> str:
    """Caminho particionado por entidade/ano/mes/dia da extração."""
    return (
        f"{entity}/ano={extracted_at:%Y}/mes={extracted_at:%m}/dia={extracted_at:%d}/"
        f"{entity}_{extracted_at:%Y%m%dT%H%M%S}_{run_id[:8]}_{batch_number:04d}.json"
    )


def write_batch(
    s3, bucket: str, entity: str, records: list[dict], *,
    extracted_at: datetime, source: str, run_id: str, batch_number: int, last_id_param: int,
) -> str:
    # Envelope: metadados ficam fora de "data", e "data" é exatamente o que a API devolveu.
    body = {
        "_extracted_at": extracted_at.isoformat(),
        "_source": source,
        "_run_id": run_id,
        "_entity": entity,
        "_last_id_param": last_id_param,
        "_record_count": len(records),
        "data": records,
    }
    key = batch_key(entity, extracted_at, run_id, batch_number)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    return key


def read_batch(s3, bucket: str, key: str) -> dict:
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())


def list_keys(s3, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    return sorted(keys)
