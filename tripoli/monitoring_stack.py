# tripoli/monitoring_stack.py

import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_sns as sns
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from constructs import Construct


class MonitoringStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ingestion_lambda_name = "tripolis-log-ingestion"
        report_lambda_name = "tripolis-daily-report"
        raw_bucket_name = "tripolis-backup-raw"
        report_topic_name = "tripolis-daily-report-topic"

        dashboard = cloudwatch.Dashboard(
            self,
            "TripolisPizzaDashboard",
            dashboard_name="TripolisPizza-CloudDashboard",
        )

        def lambda_metric(function_name: str, metric_name: str,
                          statistic: str = "Sum",
                          period_minutes: int = 5) -> cloudwatch.Metric:
            return cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name=metric_name,
                dimensions_map={"FunctionName": function_name},
                statistic=statistic,
                period=Duration.minutes(period_minutes),
            )

        def s3_metric(bucket_name: str, metric_name: str,
                      storage_type: str,
                      period_hours: int = 1) -> cloudwatch.Metric:
            return cloudwatch.Metric(
                namespace="AWS/S3",
                metric_name=metric_name,
                dimensions_map={
                    "BucketName": bucket_name,
                    "StorageType": storage_type,
                },
                statistic="Average",
                period=Duration.hours(period_hours),
            )


        ingestion_invocations = lambda_metric(
            ingestion_lambda_name, "Invocations"
        )
        ingestion_errors = lambda_metric(
            ingestion_lambda_name, "Errors"
        )

        # Success ratio = successful executions / total executions
        # = IF(invocations > 0, (invocations - errors) / invocations, 1)
        ingestion_success_ratio = cloudwatch.MathExpression(
            expression="IF(inv > 0, (inv - err) / inv, 1)",
            using_metrics={
                "inv": ingestion_invocations,
                "err": ingestion_errors,
            },
            period=Duration.minutes(5),
            label="Ingestion Success Ratio",
        )

        ratio_alarm = ingestion_success_ratio.create_alarm(
            self,
            "IngestionSuccessRatioLow",
            threshold=0.95,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        )

        # SNS Topic for alarm notifications
        alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name="tripolis-alarm-topic",
        )

        # Attach SNS action to the ratio alarm
        ratio_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(alarm_topic)
        )

        # S3 ingestion / storage metrics (raw bucket)
        raw_object_count = s3_metric(
            raw_bucket_name, "NumberOfObjects", "AllStorageTypes"
        )
        raw_bucket_size = s3_metric(
            raw_bucket_name, "BucketSizeBytes", "StandardStorage"
        )

        # Storage-class breakdown for distribution (pie)
        raw_standard_objects = s3_metric(
            raw_bucket_name, "NumberOfObjects", "StandardStorage"
        )
        raw_standard_ia_objects = s3_metric(
            raw_bucket_name, "NumberOfObjects", "StandardIAStorage"
        )
        raw_intelligent_objects = s3_metric(
            raw_bucket_name, "NumberOfObjects", "IntelligentTieringFAStorage"
        )

        # Report Lambda metrics
        report_duration = lambda_metric(
            report_lambda_name, "Duration", statistic="p95"
        )
        report_errors = lambda_metric(
            report_lambda_name, "Errors"
        )

        # SNS metrics (email delivery for daily report)
        sns_notifications_delivered = cloudwatch.Metric(
            namespace="AWS/SNS",
            metric_name="NumberOfNotificationsDelivered",
            dimensions_map={"TopicName": report_topic_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        sns_notifications_failed = cloudwatch.Metric(
            namespace="AWS/SNS",
            metric_name="NumberOfNotificationsFailed",
            dimensions_map={"TopicName": report_topic_name},
            statistic="Sum",
            period=Duration.minutes(5),
        )

        # DASHBOARD LAYOUT
        dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown=(
                    "# Tripolis Pizza Backup Monitoring\n"
                    "Tracks ingestion health (success ratio), S3 backups, the daily "
                    "report Lambda, SNS email delivery, and alarm notifications."
                ),
                width=24,
                height=2,
            )
        )

        # Row 1: Ingestion success ratio + alarm
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Ingestion Success Ratio (Successful / Total)",
                left=[ingestion_success_ratio],
                width=16,
            ),
            cloudwatch.AlarmWidget(
                title="ALARM: Ingestion Success Ratio < 0.95",
                alarm=ratio_alarm,
                width=8,
            ),
        )

        # Row 2: S3 backups (how much has been ingested)
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Raw Backup Bucket: Files & Size",
                left=[raw_object_count],
                right=[raw_bucket_size],
                width=24,
            ),
        )

        # Row 3: Reporting path health (Lambda + SNS)
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Report Lambda: Duration & Errors",
                left=[report_duration],
                right=[report_errors],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="SNS Delivery Health (Delivered vs Failed)",
                left=[sns_notifications_delivered, sns_notifications_failed],
                width=12,
            ),
        )

        # Row 4: Storage class distribution (visually shows ratio of classes)
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Raw Bucket Storage Classes (Distribution)",
                left=[
                    raw_standard_objects,
                    raw_standard_ia_objects,
                    raw_intelligent_objects,
                ],
                view=cloudwatch.GraphWidgetView.PIE,
                width=24,
            ),
        )
