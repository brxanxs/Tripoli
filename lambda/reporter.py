import boto3
from datetime import datetime, timezone, timedelta
import io
import csv
import json

IN_BUCKET = 'TempBucket'
OUT_BUCKET = 'ReportBucket'

s3 = boto3.client('s3')

def lambda_handler(event, context):
    
    time_prev = datetime.now(timezone.utc) - timedelta(hours = 24)
    filename_list = []

    pagin = s3.get_paginator('list_objects_v2')
    pages = pagin.paginate(Bucket = IN_BUCKET)

    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                last_mod = obj['LastModified']
                if last_mod > time_prev:
                    filename_list.append({'filename' : obj['Key'], 'uploaded' : last_mod })
    
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = ['Filename', 'Date_Uploaded']
    writer.writerow(header)

    for row in filename_list:
        writer.writerow([row['filename', 'uploaded']])

    content = buffer.getvalue()

    
