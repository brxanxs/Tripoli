import os
import json
import boto3


def main(event, context):
    s3 = boto3.client('s3')
    key = event.get('queryStringParameters', {}).get('filename', 'default.dat')
    bucket = os.environ['BUCKET_NAME']


    url = s3.generate_presigned_url(
    'put_object',
    Params={'Bucket': bucket, 'Key': key},
    ExpiresIn=3600
    )


    return {
    'statusCode': 200,
    'body': json.dumps({ 'uploadUrl': url })
    }