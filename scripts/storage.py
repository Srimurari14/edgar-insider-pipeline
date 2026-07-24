import os
import shutil
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from scripts.config import LOCAL_ROOT, S3_BUCKET, USE_S3

s3 = boto3.client("s3")


def _local_path(key):
    return os.path.join(LOCAL_ROOT, key)


def write_bytes(key, data):
    # uploads raw data directly to s3 bucket
    if USE_S3:
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data)
    else:
        path = _local_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)


def read_bytes(key):
    # downloads and reads the conetent of an existing file from S3 into memory
    if USE_S3:
        return s3.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
    else:
        path = _local_path(key)
        with open(path, "rb") as f:
            return f.read()


def exists(key):
    # checks whether a specific file path exists in s3 bucket without downloading
    if USE_S3:
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise
    else:
        path = _local_path(key)
        return os.path.isfile(path)


def list_files(prefix):
    # finds and lists paths of all files inside a specific folder or matching naming pattern
    if USE_S3:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"]
    else:
        root = Path(_local_path(prefix))
        if not root.exists():
            return
        for p in root.rglob("*"):
            if p.is_file():
                yield os.path.relpath(p, LOCAL_ROOT)


def delete_prefix(prefix):
    # deletes a specific folder and all its contents
    if USE_S3:
        keys_to_delete = list(list_files(prefix))
        if not keys_to_delete:
            return
        for i in range(0, len(keys_to_delete), 1000):
            batch = [{"Key": k} for k in keys_to_delete[i : i + 1000]]
            s3.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": batch})
    else:
        shutil.rmtree(_local_path(prefix), ignore_errors=True)
