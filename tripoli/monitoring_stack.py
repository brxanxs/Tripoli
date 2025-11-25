# tripoli/monitoring_stack.py

import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from constructs import Construct


class MonitoringStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_ingestion_lambda_name = "tripolis-log-ingestion"
        glacier_archive_lambda_name = "tripolis-glacier-archive"
        daily_report_lambda_name = "tripolis-daily-report"

        logs_queue_name = "tripolis-backup-logs"
        backup_bucket_name = "tripolis-backup-raw"
        archive_bucket_name = "tripolis-backup-archive"
        report_topic_name = "tripolis-daily-report-topic"

        # Creating the CloudWatch dashboard
        dashboard = cloudwatch.Dashboard(
            self,
            "TripolisPizzaDashboard",
            dashboard_name="TripolisPizza-CloudDashboard",
        )

        # ============================================================
        # 1) INCOMING DATA: SQS + LOG INGESTION LAMBDA
        # ============================================================

        # How many log messages are entering the system
        sqs_messages_sent = cloudwatch.Metric(
            namespace="AWS/SQS",
            metric_name="NumberOfMessagesSent",
            dimensions_map={"QueueName": logs_queue_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        # How many messages are still waiting to be processed
        sqs_backlog = cloudwatch.Metric(
            namespace="AWS/SQS",
            metric_name="ApproximateNumberOfMessagesVisible",
            dimensions_map={"QueueName": logs_queue_name},
            statistic="Average",
            period=Duration.minutes(5),
        )

        # Log ingestion Lambda metrics
        ingestion_invocations = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Invocations",
            dimensions_map={"FunctionName": log_ingestion_lambda_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        ingestion_errors = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Errors",
            dimensions_map={"FunctionName": log_ingestion_lambda_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        ingestion_duration = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Duration",
            dimensions_map={"FunctionName": log_ingestion_lambda_name},
            statistic="p95",
            period=Duration.minutes(5),
        )

        # ============================================================
        # 2) DAILY BACKUP COUNT
        # ============================================================

        daily_backup_count = cloudwatch.Metric(
            namespace="TripolisPizza/ReportingSystem",
            metric_name="DailyBackupCount",
            statistic="Sum",
            period=Duration.days(1),
        )

        # ============================================================
        # 3) SERVICE HEALTH: SQS + S3 (BACKUP + ARCHIVE)
        # ============================================================

        # SQS Queue Age: are we falling behind?
        sqs_age = cloudwatch.Metric(
            namespace="AWS/SQS",
            metric_name="ApproximateAgeOfOldestMessage",
            dimensions_map={"QueueName": logs_queue_name},
            statistic="Maximum",
            period=Duration.minutes(5),
        )

        # S3 current backup bucket
        backup_objects = cloudwatch.Metric(
            namespace="AWS/S3",
            metric_name="NumberOfObjects",
            dimensions_map={
                "BucketName": backup_bucket_name,
                "StorageType": "AllStorageTypes",
            },
            statistic="Average",
            period=Duration.hours(1),
        )

        backup_size = cloudwatch.Metric(
            namespace="AWS/S3",
            metric_name="BucketSizeBytes",
            dimensions_map={
                "BucketName": backup_bucket_name,
                "StorageType": "StandardStorage",
            },
            statistic="Average",
            period=Duration.hours(1),
        )

        # S3 archive bucket (Glacier)
        archive_objects = cloudwatch.Metric(
            namespace="AWS/S3",
            metric_name="NumberOfObjects",
            dimensions_map={
                "BucketName": archive_bucket_name,
                "StorageType": "AllStorageTypes",
            },
            statistic="Average",
            period=Duration.hours(1),
        )

        archive_size = cloudwatch.Metric(
            namespace="AWS/S3",
            metric_name="BucketSizeBytes",
            dimensions_map={
                "BucketName": archive_bucket_name,
                "StorageType": "StandardStorage",
            },
            statistic="Average",
            period=Duration.hours(1),
        )

        # ============================================================
        # 4) GLACIER ARCHIVE LAMBDA
        # ============================================================

        glacier_errors = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Errors",
            dimensions_map={"FunctionName": glacier_archive_lambda_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        glacier_duration = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Duration",
            dimensions_map={"FunctionName": glacier_archive_lambda_name},
            statistic="p95",
            period=Duration.minutes(5),
        )

        # ============================================================
        # 5) DAILY REPORT LAMBDA + SNS
        # ============================================================

        report_errors = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Errors",
            dimensions_map={"FunctionName": daily_report_lambda_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        report_duration = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Duration",
            dimensions_map={"FunctionName": daily_report_lambda_name},
            statistic="p95",
            period=Duration.minutes(5),
        )

        sns_delivered = cloudwatch.Metric(
            namespace="AWS/SNS",
            metric_name="NumberOfNotificationsDelivered",
            dimensions_map={"TopicName": report_topic_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        sns_failed = cloudwatch.Metric(
            namespace="AWS/SNS",
            metric_name="NumberOfNotificationsFailed",
            dimensions_map={"TopicName": report_topic_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        # ============================================================
        # 6) ALARM: DAILY BACKUPS TOO LOW OVER 7 DAYS
        # ============================================================

        low_backup_alarm = daily_backup_count.create_alarm(
            self,
            "LowBackupAlarm",
            threshold=6,
            evaluation_periods=7,  # over the last 7 days
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        )

        # ========== ROW 1: SQS Incoming Logs & Queue Health ==========
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Incoming Logs (SQS Messages Sent)",
                left=[sqs_messages_sent],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="SQS Backlog (Messages Waiting)",
                left=[sqs_backlog],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="SQS Queue Age (Oldest Message)",
                left=[sqs_age],
                width=8,
            ),
        )

        # ========== ROW 2: Ingestion Lambda & Glacier Archive Lambda ==========
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Log Ingestion Lambda: Invocations & Errors",
                left=[ingestion_invocations],
                right=[ingestion_errors],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Log Ingestion Lambda: Duration (p95)",
                left=[ingestion_duration],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Glacier Archive Lambda: Duration & Errors",
                left=[glacier_duration],
                right=[glacier_errors],
                width=8,
            ),
        )

        # ========== ROW 3: Storage & Daily Backup Count ==========
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="S3 Current Backups: Objects & Size",
                left=[backup_objects],
                right=[backup_size],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="S3 Archive (Glacier) Bucket: Objects & Size",
                left=[archive_objects],
                right=[archive_size],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Daily Backup Count",
                left=[daily_backup_count],
                width=8,
            ),
        )

        # ========== ROW 4: Reporting Lambda, SNS Health, Alarm ==========
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Daily Report Lambda: Duration & Errors",
                left=[report_duration],
                right=[report_errors],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="SNS Report Delivery Health",
                left=[sns_delivered, sns_failed],
                width=8,
            ),
            cloudwatch.AlarmWidget(
                title="Daily Backups < 6 (7-day Alarm)",
                alarm=low_backup_alarm,
                width=8,
            ),
        )        
