import json
import os
import boto3

ssm = boto3.client("ssm")
s3 = boto3.client("s3")

def main(event, context):
    # Get bucketMap with env and SSM
    paramName = os.environ["SSM_logBucketMap_PARAM"]
    resp = ssm.get_parameter(Name=paramName)
    bucketMap = json.loads(resp["Parameter"]["Value"])

    # Get API key ID from request context
    keyID = event.get("requestContext", {}).get("identity", {}).get("apiKeyId")
    if not keyID:
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "API key missing"})
        }

    # Get bucketName from key ID
    bucketName = bucketMap.get(keyID)
    if not bucketName:
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Invalid API key"})
        }

    # Get key from body
    body = json.loads(event.get("body", "{}"))
    key = body.get("key")
    if not key:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing key in request"})
        }

    # Generate pre-signed PUT URL
    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucketName, "Key": key},
        ExpiresIn=int(os.environ.get("URL_EXPIRATION", 3600))
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"url": url, "bucket": bucketName, "key": key})
    }