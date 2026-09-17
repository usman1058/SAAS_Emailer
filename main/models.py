from django.db import models


class SentEmailHash(models.Model):
    """Model to store sent email hashes for deduplication."""
    hash = models.CharField(max_length=64, unique=True, db_index=True)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'main_sent_email_hash'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'created_at']),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class SendJob(models.Model):
    """Model to track email sending jobs and provide kill switch."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('stopped', 'Stopped by user'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.BigAutoField(primary_key=True)
    sender_email = models.EmailField()
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_duplicates = models.PositiveIntegerField(default=0)
    skipped_invalid = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'main_send_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Job #{self.id} - {self.status} - {self.sender_email}"

    @property
    def is_active(self):
        return self.status == 'running'

    @property
    def progress_percent(self):
        if self.total_recipients == 0:
            return 0
        return round((self.sent_count + self.failed_count + self.skipped_duplicates + self.skipped_invalid) / self.total_recipients * 100, 1)