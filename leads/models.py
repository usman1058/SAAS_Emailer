from django.db import models


class SearchJob(models.Model):
    """Model to track OSM lead search jobs."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    city = models.CharField(max_length=255)
    country = models.CharField(max_length=255, blank=True)
    categories = models.JSONField(default=list)  # List of category strings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_found = models.PositiveIntegerField(default=0)
    no_website_count = models.PositiveIntegerField(default=0)
    priority_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'leads_search_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['city', 'country']),
        ]

    def __str__(self):
        return f"Search #{self.id} - {self.city}, {self.country} ({self.status})"

    @property
    def is_active(self):
        return self.status == 'running'


class Lead(models.Model):
    """Model to store business leads from OSM."""
    search_job = models.ForeignKey(
        SearchJob, on_delete=models.CASCADE, related_name='leads'
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    address = models.TextField(blank=True, default='')
    phone = models.CharField(max_length=100, blank=True, default='')
    website = models.URLField(blank=True, default='')
    has_website = models.BooleanField(default=False)
    whatsapp_status = models.CharField(max_length=100, blank=True, default='')
    whatsapp_check_link = models.URLField(blank=True, default='')
    osm_url = models.URLField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'leads_lead'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['search_job', 'has_website']),
            models.Index(fields=['search_job', 'whatsapp_status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.category}) - {'Website' if self.has_website else 'No Website'}"

    @property
    def is_priority(self):
        """Priority lead: no website AND mobile number."""
        return not self.has_website and self.whatsapp_status.startswith('Mobile')


class ExportFile(models.Model):
    """Model to track exported files."""
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('html', 'HTML Report'),
    ]

    search_job = models.ForeignKey(
        SearchJob, on_delete=models.CASCADE, related_name='exports'
    )
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'leads_export_file'
        ordering = ['-created_at']

    def __str__(self):
        return f"Export #{self.id} - {self.file_format} for Job #{self.search_job_id}"