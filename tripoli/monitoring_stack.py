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

        backup_bucket_name = "tripolis-backup-raw"
        archive_bucket_name = "tripolis-backup-archive"
        report_topic_name = "tripolis-daily-report-topic"

        dashboard = cloudwatch.Dashboard(
            self,
            "TripolisPizzaDashboard",
            dashboard_name="TripolisPizza-CloudDashboard",
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

        # Daily backup custom metric
        daily_backup_count = cloudwatch.Metric(
            namespace="TripolisPizza/ReportingSystem",
            metric_name="DailyBackupCount",
            statistic="Sum",
            period=Duration.days(1),
        )

        # S3: current backup bucket
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

        # S3: archive / Glacier bucket
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

        # Glacier archive Lambda
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

        # Daily report Lambda
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

        # SNS report topic
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

        # If daily backups too low over 7 days
        low_backup_alarm = daily_backup_count.create_alarm(
            self,
            "LowBackupAlarm",
            threshold=6,  # fewer than 6 backups/day is a problem
            evaluation_periods=7,  # over the last 7 days
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        )

        # ROW 1
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
                title="Daily Backup Count",
                left=[daily_backup_count],
                width=8,
            ),
        )

        # ROW 2
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
                title="Glacier Archive Lambda: Duration & Errors",
                left=[glacier_duration],
                right=[glacier_errors],
                width=8,
            ),
        )

        # ROW 3
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
