import boto3
from datetime import datetime, timezone, timedelta
import io
import csv
import os

def lambda_handler(event, context):

    s3 = boto3.client("s3")
    sns = boto3.client("sns")

    IN_BUCKET = os.environ.get("INPUT_BUCKET_NAME")
    OUT_BUCKET = os.environ.get("OUTPUT_BUCKET_NAME")
    SNS_ARN  = os.environ.get("REPORTER_SNS_ARN")

    CUTOFF = os.environ.get("CUTOFF_HOUR")
    EXPIRE = os.environ.get("REPORT_URL_EXPIRATION_SECONDS")
    
    CUTOFF_FLOAT = float(CUTOFF)
    EXPIRE_INT = int(EXPIRE)
    
    time_prev = datetime.now(timezone.utc) - timedelta(hours = CUTOFF_FLOAT)
    filename_list = []

    pagin = s3.get_paginator("list_objects_v2")
    pages = pagin.paginate(Bucket = IN_BUCKET)

    for page in pages:
        if "Contents" in page:
            for obj in page["Contents"]:
                last_mod = obj["LastModified"]
                if last_mod > time_prev:
                    filename_list.append({"filename" : obj["Key"], "uploaded" : last_mod })
    
    stream = io.StringIO()
    writer = csv.writer(stream)
    header = ["Filename", "Date_Uploaded"]
    writer.writerow(header)

    for row in filename_list:
        writer.writerow([row["filename"], row["uploaded"]])

    content = stream.getvalue()

    time_now = datetime.now(timezone.utc)
    bucket_key = f"report-{time_now}.csv"
    
    s3.put_object(
        Bucket = OUT_BUCKET,
        Key = bucket_key,
        Body = content,
        ContentType = "text/csv"
    )

    url = s3.generate_presigned_url(
        ClientMethod = "get_object",
        Params = {"Bucket": OUT_BUCKET, "Key": bucket_key},
        ExpiresIn = EXPIRE_INT
    )

    subject = "File Report"
    body = f"{url}"

    sns.publish(
        TopicArn = SNS_ARN,
        Message = body,
        Subject = subject
    )

    return {
        "statusCode" : 200,
        "headers" : {"Content-Type" : "text/plain"},
        "body" : "Report published!"
    }
