from datetime import datetime
from typing import Dict, Optional, Any
from jinja2 import Environment, PackageLoader, select_autoescape
import boto3
from botocore.exceptions import ClientError

from infrastructure.config import Settings
from infrastructure.logging import get_logger
from infrastructure.exceptions import NotificationDeliveryException
from domain.models import NotificationType, NotificationPriority

logger = get_logger(__name__)

class NotificationTemplate:
    def __init__(self):
        self.env = Environment(
            loader=PackageLoader('infrastructure', 'templates'),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a notification template with the given context
        """
        try:
            template = self.env.get_template(f"{template_name}.html")
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {str(e)}")
            raise NotificationDeliveryException(
                detail=f"Template rendering failed: {str(e)}",
                provider="template_engine"
            )

class NotificationDispatcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sns_client = boto3.client(
            'sns',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.sqs_client = boto3.client(
            'sqs',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.template_engine = NotificationTemplate()

    async def dispatch(
        self,
        notification_type: NotificationType,
        recipient: str,
        subject: str,
        content: Dict[str, Any],
        priority: NotificationPriority,
        template_name: Optional[str] = None
    ) -> str:
        """
        Dispatch a notification to the appropriate queue based on type and priority
        """
        try:
            # Render template if provided
            if template_name:
                rendered_content = self.template_engine.render(template_name, content)
            else:
                rendered_content = str(content)

            # Prepare message attributes
            message_attributes = {
                'NotificationType': {
                    'DataType': 'String',
                    'StringValue': notification_type
                },
                'Priority': {
                    'DataType': 'String',
                    'StringValue': priority
                },
                'Timestamp': {
                    'DataType': 'String',
                    'StringValue': datetime.utcnow().isoformat()
                }
            }

            # Select queue based on priority
            queue_url = self._get_queue_url(priority)

            # Send message to SQS
            response = self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=rendered_content,
                MessageAttributes=message_attributes,
                MessageGroupId=recipient  # For FIFO queues
            )

            logger.info(
                "Notification dispatched successfully",
                extra={
                    "message_id": response['MessageId'],
                    "notification_type": notification_type,
                    "priority": priority,
                    "recipient": recipient
                }
            )

            return response['MessageId']

        except ClientError as e:
            logger.error(
                "Failed to dispatch notification",
                extra={
                    "error": str(e),
                    "notification_type": notification_type,
                    "priority": priority,
                    "recipient": recipient
                }
            )
            raise NotificationDeliveryException(
                detail=f"Failed to dispatch notification: {str(e)}",
                provider="aws_sqs"
            )

    async def send_immediate(
        self,
        notification_type: NotificationType,
        recipient: str,
        subject: str,
        content: Dict[str, Any],
        template_name: Optional[str] = None
    ) -> str:
        """
        Send a notification immediately without queueing (for high-priority notifications)
        """
        try:
            # Render template if provided
            if template_name:
                rendered_content = self.template_engine.render(template_name, content)
            else:
                rendered_content = str(content)

            if notification_type == NotificationType.EMAIL:
                return await self._send_email(recipient, subject, rendered_content)
            elif notification_type == NotificationType.SMS:
                return await self._send_sms(recipient, rendered_content)
            else:
                raise ValueError(f"Unsupported notification type: {notification_type}")

        except Exception as e:
            logger.error(
                "Failed to send immediate notification",
                extra={
                    "error": str(e),
                    "notification_type": notification_type,
                    "recipient": recipient
                }
            )
            raise NotificationDeliveryException(
                detail=f"Failed to send immediate notification: {str(e)}",
                provider=notification_type
            )

    async def _send_email(self, recipient: str, subject: str, content: str) -> str:
        """
        Send an email using AWS SES
        """
        try:
            response = self.sns_client.publish(
                TopicArn=self.settings.SNS_EMAIL_TOPIC_ARN,
                Message=content,
                Subject=subject,
                MessageAttributes={
                    'email': {
                        'DataType': 'String',
                        'StringValue': recipient
                    }
                }
            )
            return response['MessageId']
        except ClientError as e:
            raise NotificationDeliveryException(
                detail=f"Failed to send email: {str(e)}",
                provider="aws_ses"
            )

    async def _send_sms(self, recipient: str, content: str) -> str:
        """
        Send an SMS using AWS SNS
        """
        try:
            response = self.sns_client.publish(
                PhoneNumber=recipient,
                Message=content,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            return response['MessageId']
        except ClientError as e:
            raise NotificationDeliveryException(
                detail=f"Failed to send SMS: {str(e)}",
                provider="aws_sns"
            )

    def _get_queue_url(self, priority: NotificationPriority) -> str:
        """
        Get the appropriate SQS queue URL based on priority
        """
        priority_queue_mapping = {
            NotificationPriority.HIGH: self.settings.SQS_HIGH_PRIORITY_QUEUE_URL,
            NotificationPriority.MEDIUM: self.settings.SQS_MEDIUM_PRIORITY_QUEUE_URL,
            NotificationPriority.LOW: self.settings.SQS_LOW_PRIORITY_QUEUE_URL
        }
        return priority_queue_mapping[priority]

class NotificationProcessor:
    def __init__(self, settings: Settings, dispatcher: NotificationDispatcher):
        self.settings = settings
        self.dispatcher = dispatcher
        self.sqs_client = boto3.client(
            'sqs',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )

    async def process_queued_notifications(self) -> None:
        """
        Process notifications from SQS queues based on priority
        """
        priority_queues = [
            (NotificationPriority.HIGH, self.settings.SQS_HIGH_PRIORITY_QUEUE_URL),
            (NotificationPriority.MEDIUM, self.settings.SQS_MEDIUM_PRIORITY_QUEUE_URL),
            (NotificationPriority.LOW, self.settings.SQS_LOW_PRIORITY_QUEUE_URL)
        ]

        for priority, queue_url in priority_queues:
            try:
                # Receive messages from queue
                response = self.sqs_client.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=10,
                    MessageAttributeNames=['All'],
                    WaitTimeSeconds=20
                )

                messages = response.get('Messages', [])
                for message in messages:
                    try:
                        # Process the message
                        await self._process_message(message)
                        
                        # Delete the message from the queue
                        self.sqs_client.delete_message(
                            QueueUrl=queue_url,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to process message",
                            extra={
                                "error": str(e),
                                "message_id": message.get('MessageId'),
                                "priority": priority
                            }
                        )

            except Exception as e:
                logger.error(
                    f"Failed to process queue",
                    extra={
                        "error": str(e),
                        "priority": priority,
                        "queue_url": queue_url
                    }
                )

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """
        Process a single notification message from the queue
        """
        message_attributes = message.get('MessageAttributes', {})
        notification_type = message_attributes.get('NotificationType', {}).get('StringValue')
        
        if not notification_type:
            raise ValueError("Message missing NotificationType attribute")

        # Extract recipient from message attributes or message body
        recipient = self._extract_recipient(message)
        
        # Send the notification
        if notification_type == NotificationType.EMAIL:
            subject = message_attributes.get('Subject', {}).get('StringValue', 'Notification')
            await self.dispatcher.send_immediate(
                notification_type=NotificationType.EMAIL,
                recipient=recipient,
                subject=subject,
                content={"body": message['Body']}
            )
        elif notification_type == NotificationType.SMS:
            await self.dispatcher.send_immediate(
                notification_type=NotificationType.SMS,
                recipient=recipient,
                subject="",
                content={"message": message['Body']}
            )

    def _extract_recipient(self, message: Dict[str, Any]) -> str:
        """
        Extract recipient from message attributes or body
        """
        message_attributes = message.get('MessageAttributes', {})
        
        # Try to get recipient from message attributes
        if 'Recipient' in message_attributes:
            return message_attributes['Recipient']['StringValue']
            
        # Try to parse from message body
        try:
            import json
            body = json.loads(message['Body'])
            return body.get('recipient')
        except (json.JSONDecodeError, KeyError):
            raise ValueError("Unable to extract recipient from message")