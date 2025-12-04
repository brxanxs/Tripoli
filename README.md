# Overview

The stack enables clients to authenticate and directly upload objects, such as logs, to an S3 bucket using presigned URLs generated as needed. This is done with three main parts: an Amazon REST API Gateway endpoint, an AWS Lambda function for URL generation, and an S3 bucket per datacenter. Below are the instructions...

---

# 1. Client Requests a Presigned URL
A client begins with a POST request with their dedicated API key to the `/gen-url` resource. Each API key is linked to an S3 bucket using SSM Parameter Store.

---

# 2. Lambda Generates a Presigned URL
The Lambda function loads the map from SSM Parameter Store to resolve the bucket from the requestor's API key. It then generates a presigned PUT URL using AWS SDK with a 1‑hour expiration.

**Notable Lambda permissions:**
- `ssm:GetParameter` — access the map
- `s3:putObject` — upload to the corresponding bucket

---

# 3. Client Uploads to S3
With the presigned URL, the client performs a direct PUT request to the S3 bucket.

**S3 bucket controls include:**
- Server‑side encryption (SSE‑S3)
- Public access blocked unless manually overridden
- Automatic transition & deletion lifecycle rules

**Lifecycle storage classes:**
- `<30 days:` Standard
- `30–90 days:` Infrequent Access
- `90–180 days:` Glacier Instant Retrieval
- `180 days–2 years:` Glacier
- `>2 years:` Deep Archive
- `5 years:` Deletion

---

# CloudWatch Dashboard (Monitoring)
This project includes a CloudWatch dashboard that tracks:

- Ingestion success ratio for `tripolis-log-ingestion`
- Total objects and size of the S3 backup bucket
- Storage‑class distribution (Standard, IA, Glacier IR, Glacier, Deep Archive)
- Daily report Lambda duration and errors (`tripolis-daily-report`)
- SNS delivery metrics for daily report emails

An alarm triggers if the ingestion success ratio drops below `0.95` and sends notifications via the SNS topic.

**Screenshots (to be added):**
- Dashboard Overview
- Ingestion Ratio & Alarm
- S3 Metrics
- Storage Class Pie Chart
- Lambda & SNS Metrics

> **Note:**
> S3 storage metrics (`NumberOfObjects`, `BucketSizeBytes`) do **not** update in real time.
>
> AWS refreshes these once every 24 hours, and new buckets may require several hours before the first datapoint appears.
>
> The "Raw Backup Bucket: Files & Size" widget may show **"No data available"** temporarily. This is expected AWS behavior.
>
> For real‑time ingestion activity, use **S3 `PutRequests`**.

---

# Daily Report Generation
Reports are automatically generated **daily** so subscribers can see which files were uploaded in the last 24 hours.

---

## SNS Topic (Subscription Service)
All subscribers in the SNS topic **`ReportSNS`** receive the daily report.

### How to Subscribe
In the deployment stack code, add your email to the variable **`REPORTSUB`**. You will receive a confirmation email which must be approved.

<img width="806" height="400" alt="SubscriberNotification" src="https://github.com/user-attachments/assets/d54dbbbd-ed01-46ac-9fef-21f123ef5ec8" />

---

## EventBridge (Scheduler)
The EventBridge rule **`ReportSchedule`** triggers report generation daily.

- **Default:** 11:00 AM UTC
- **Customization:** Modify the cron expression in the stack to change the schedule.

<img width="806" height="499" alt="ReportURL" src="https://github.com/user-attachments/assets/b93312a2-ae92-4710-b9c5-115d7c3abbae" />

---

## Lambda (Report Generator)
The report is created by the Lambda function **`ReporterLambda`** and delivered as a CSV file.

### Process
1. Lambda compiles a list of files uploaded in the last 24 hours.
2. The CSV report is uploaded to the S3 bucket **`ReportBucket`**.
3. SNS sends an email containing a secure download link.

### Configurable Environment Variables
- **`CUTOFF_HOUR`** — Hours to look back for uploads (default: 24)
- **`REPORT_URL_EXPIRATION_SECONDS`** — How long the download link remains active (default: 24 hours)

<img width="612" height="521" alt="Report" src="https://github.com/user-attachments/assets/6bf39f70-54bf-41d1-86c7-6d13db0656bb" />

