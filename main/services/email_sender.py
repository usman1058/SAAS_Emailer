"""
Email Sending Service

Extracted from views.py to provide a clean, testable service layer.
"""
import hashlib
import logging
import mimetypes
import os
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr
from typing import Generator, Optional

import pandas as pd
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import SendJob, SentEmailHash

logger = logging.getLogger(__name__)


class EmailSenderService:
    """Service class for sending bulk emails with deduplication and kill switch."""

    def __init__(self, job: SendJob):
        self.job = job
        self.fs = FileSystemStorage()
        self.sent_hashes: set[str] = set()
        self._load_sent_hashes()

    def _load_sent_hashes(self) -> None:
        """Load previously sent email hashes from database."""
        self.sent_hashes = set(
            SentEmailHash.objects.values_list('hash', flat=True)
        )

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format using Django's validator."""
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    def _connect_smtp(self, sender_email: str, sender_password: str) -> tuple[Optional[smtplib.SMTP], Optional[str]]:
        """Establish SMTP connection with Gmail."""
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            return server, None
        except Exception as e:
            logger.error(f"SMTP login failed for {sender_email}: {e}")
            return None, f"Login failed: {e}"

    def _get_mime_type(self, file_path: str) -> tuple[str, str]:
        """Guess MIME type from file extension."""
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            main_type, sub_type = mime_type.split('/')
            return main_type, sub_type
        return 'application', 'octet-stream'

    def _build_email_message(
        self,
        sender_email: str,
        recipient: str,
        subject: str,
        personalized_message: str,
        attachment_path: Optional[str] = None,
        attachment_name: Optional[str] = None,
    ) -> EmailMessage:
        """Build an EmailMessage object."""
        msg = EmailMessage()
        msg['From'] = formataddr(("KenesisnTech", sender_email))
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.set_content(personalized_message)

        if attachment_path and os.path.exists(attachment_path):
            main_type, sub_type = self._get_mime_type(attachment_path)
            with open(attachment_path, 'rb') as f:
                msg.add_attachment(
                    f.read(),
                    maintype=main_type,
                    subtype=sub_type,
                    filename=attachment_name or os.path.basename(attachment_path),
                )

        return msg

    def _compute_message_hash(self, recipient: str, personalized_message: str) -> str:
        """Compute SHA256 hash for deduplication."""
        return hashlib.sha256((recipient + personalized_message).encode()).hexdigest()

    def _save_sent_hash(self, msg_hash: str, recipient: str, subject: str) -> None:
        """Save sent email hash to database."""
        SentEmailHash.objects.get_or_create(
            hash=msg_hash,
            defaults={'recipient': recipient, 'subject': subject},
        )
        self.sent_hashes.add(msg_hash)

    def send_emails(
        self,
        sender_email: str,
        sender_password: str,
        subject: str,
        message_template: str,
        excel_file,
        attachment=None,
    ) -> Generator[str, None, None]:
        """
        Send bulk emails and yield progress messages.

        Yields:
            str: Progress/log messages for streaming response.
        """
        # Initialize job
        self.job.status = 'running'
        self.job.started_at = timezone.now()
        self.job.save(update_fields=['status', 'started_at'])

        yield "Starting email sending...\n"

        server, login_error = self._connect_smtp(sender_email, sender_password)
        if login_error:
            yield f"Login failed: {login_error}\n"
            self.job.status = 'failed'
            self.job.error_message = login_error
            self.job.save(update_fields=['status', 'error_message'])
            return

        try:
            # Read Excel file
            excel_path = self.fs.save(excel_file.name, excel_file)
            df = pd.read_excel(self.fs.path(excel_path))

            # Validate required columns
            if 'Email' not in df.columns:
                yield "Error: Excel file must have an 'Email' column.\n"
                self.job.status = 'failed'
                self.job.error_message = "Missing 'Email' column in Excel file"
                self.job.save(update_fields=['status', 'error_message'])
                return

            # Handle attachment
            attachment_path = None
            attachment_name = None
            if attachment:
                attachment_path = self.fs.save(attachment.name, attachment)
                attachment_name = attachment.name

            self.job.total_recipients = len(df)
            self.job.save(update_fields=['total_recipients'])

            # Process each row
            for i, (_, row) in enumerate(df.iterrows()):
                # Check kill switch
                self.job.refresh_from_db()
                if not self.job.is_active:
                    yield "Stopped by user.\n"
                    self.job.status = 'stopped'
                    self.job.save(update_fields=['status'])
                    break

                # Get and validate recipient
                recipient = str(row.get('Email')).strip() if row.get('Email') else None
                if not recipient or not self._is_valid_email(recipient):
                    yield f"Skipping invalid or missing email: {recipient}\n"
                    self.job.skipped_invalid += 1
                    self.job.save(update_fields=['skipped_invalid'])
                    continue

                # Personalize message
                name = str(row.get('Name')).strip() if row.get('Name') else "there"
                personalized_message = message_template.replace("{{name}}", name)

                # Check deduplication
                msg_hash = self._compute_message_hash(recipient, personalized_message)
                if msg_hash in self.sent_hashes:
                    yield f"Skipping duplicate for {recipient}\n"
                    self.job.skipped_duplicates += 1
                    self.job.save(update_fields=['skipped_duplicates'])
                    continue

                # Build and send email
                msg = self._build_email_message(
                    sender_email=sender_email,
                    recipient=recipient,
                    subject=subject,
                    personalized_message=personalized_message,
                    attachment_path=self.fs.path(attachment_path) if attachment_path else None,
                    attachment_name=attachment_name,
                )

                try:
                    server.send_message(msg)
                    yield f"Sent to {recipient}\n"
                    self._save_sent_hash(msg_hash, recipient, subject)
                    self.job.sent_count += 1
                    self.job.save(update_fields=['sent_count'])

                except smtplib.SMTPServerDisconnected:
                    yield "Connection lost. Reconnecting...\n"
                    server, reconnect_error = self._connect_smtp(sender_email, sender_password)
                    if reconnect_error:
                        yield f"Reconnection failed: {reconnect_error}\n"
                        self.job.failed_count += 1
                        self.job.save(update_fields=['failed_count'])
                        break
                    try:
                        server.send_message(msg)
                        yield f"Sent to {recipient} after reconnect\n"
                        self._save_sent_hash(msg_hash, recipient, subject)
                        self.job.sent_count += 1
                        self.job.save(update_fields=['sent_count'])
                    except Exception as e:
                        yield f"Failed after reconnect: {e}\n"
                        self.job.failed_count += 1
                        self.job.save(update_fields=['failed_count'])
                        break

                except Exception as e:
                    yield f"Failed to send to {recipient}: {e}\n"
                    self.job.failed_count += 1
                    self.job.save(update_fields=['failed_count'])

                # Rate limiting
                time.sleep(getattr(settings, 'EMAIL_SEND_DELAY', 0.5))

                # Reconnect periodically
                if (i + 1) % getattr(settings, 'EMAIL_RECONNECT_BATCH', 20) == 0:
                    try:
                        server.quit()
                    except Exception:
                        pass
                    server, reconnect_error = self._connect_smtp(sender_email, sender_password)
                    if reconnect_error:
                        yield f"Periodic reconnect failed: {reconnect_error}\n"
                        break

            # Cleanup
            try:
                server.quit()
            except Exception:
                pass

            # Final status
            if self.job.status == 'running':
                self.job.status = 'completed'
            self.job.completed_at = timezone.now()
            self.job.save(update_fields=['status', 'completed_at'])

            yield "Finished sending emails.\n"

        except Exception as e:
            logger.exception("Error in send_emails")
            yield f"Error: {e}\n"
            self.job.status = 'failed'
            self.job.error_message = str(e)
            self.job.save(update_fields=['status', 'error_message'])