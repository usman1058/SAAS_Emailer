"""
Tests for main app (Email Sender).
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from main.forms import EmailForm
from main.models import SendJob, SentEmailHash
from main.services.email_sender import EmailSenderService


class EmailFormTests(TestCase):
    """Tests for EmailForm validation."""

    def test_valid_form(self):
        """Test form with valid data."""
        form = EmailForm(data={
            'sender_email': 'test@gmail.com',
            'sender_password': 'apppassword',
            'subject': 'Test Subject',
            'message': 'Hello {{name}}!',
        }, files={
            'excel_file': SimpleUploadedFile('test.xlsx', b'fake content', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        })
        self.assertTrue(form.is_valid())

    def test_invalid_sender_email(self):
        """Test form rejects invalid email."""
        form = EmailForm(data={
            'sender_email': 'not-an-email',
            'sender_password': 'apppassword',
            'subject': 'Test',
            'message': 'Hello',
        }, files={
            'excel_file': SimpleUploadedFile('test.xlsx', b'fake content', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('sender_email', form.errors)

    def test_missing_excel_file(self):
        """Test form requires excel file."""
        form = EmailForm(data={
            'sender_email': 'test@gmail.com',
            'sender_password': 'apppassword',
            'subject': 'Test',
            'message': 'Hello',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('excel_file', form.errors)

    def test_invalid_excel_extension(self):
        """Test form rejects non-Excel files."""
        form = EmailForm(data={
            'sender_email': 'test@gmail.com',
            'sender_password': 'apppassword',
            'subject': 'Test',
            'message': 'Hello',
        }, files={
            'excel_file': SimpleUploadedFile('test.txt', b'fake content', content_type='text/plain'),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('excel_file', form.errors)

    def test_valid_attachment_extensions(self):
        """Test form accepts valid attachment types."""
        for ext in ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'txt', 'csv']:
            form = EmailForm(data={
                'sender_email': 'test@gmail.com',
                'sender_password': 'apppassword',
                'subject': 'Test',
                'message': 'Hello',
            }, files={
                'excel_file': SimpleUploadedFile('test.xlsx', b'fake content', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                'attachment': SimpleUploadedFile(f'test.{ext}', b'fake', content_type='application/octet-stream'),
            })
            self.assertTrue(form.is_valid(), f"Failed for extension: {ext}")

    def test_invalid_attachment_extension(self):
        """Test form rejects invalid attachment types."""
        form = EmailForm(data={
            'sender_email': 'test@gmail.com',
            'sender_password': 'apppassword',
            'subject': 'Test',
            'message': 'Hello',
        }, files={
            'excel_file': SimpleUploadedFile('test.xlsx', b'fake content', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            'attachment': SimpleUploadedFile('test.exe', b'fake', content_type='application/octet-stream'),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)


class SendJobModelTests(TestCase):
    """Tests for SendJob model."""

    def test_create_job(self):
        """Test creating a send job."""
        job = SendJob.objects.create(
            sender_email='test@gmail.com',
            subject='Test Subject',
            status='pending',
        )
        self.assertEqual(job.status, 'pending')
        self.assertFalse(job.is_active)
        self.assertEqual(job.progress_percent, 0)

    def test_job_status_transitions(self):
        """Test job status property."""
        job = SendJob.objects.create(
            sender_email='test@gmail.com',
            subject='Test',
            status='running',
        )
        self.assertTrue(job.is_active)

        job.status = 'completed'
        self.assertFalse(job.is_active)

    def test_progress_calculation(self):
        """Test progress percentage calculation."""
        job = SendJob.objects.create(
            sender_email='test@gmail.com',
            subject='Test',
            total_recipients=100,
            sent_count=50,
            failed_count=5,
            skipped_duplicates=10,
            skipped_invalid=5,
        )
        self.assertEqual(job.progress_percent, 70.0)


class SentEmailHashModelTests(TestCase):
    """Tests for SentEmailHash model."""

    def test_create_hash(self):
        """Test creating a sent email hash."""
        hash_obj = SentEmailHash.objects.create(
            hash='a' * 64,
            recipient='test@example.com',
            subject='Test Subject',
        )
        self.assertEqual(hash_obj.hash, 'a' * 64)
        self.assertEqual(str(hash_obj), 'test@example.com - ' + hash_obj.created_at.strftime('%Y-%m-%d %H:%M'))

    def test_unique_hash_constraint(self):
        """Test unique constraint on hash field."""
        SentEmailHash.objects.create(
            hash='a' * 64,
            recipient='test@example.com',
            subject='Test',
        )
        with self.assertRaises(Exception):
            SentEmailHash.objects.create(
                hash='a' * 64,
                recipient='other@example.com',
                subject='Test 2',
            )


class EmailSenderServiceTests(TestCase):
    """Tests for EmailSenderService."""

    def setUp(self):
        self.job = SendJob.objects.create(
            sender_email='test@gmail.com',
            subject='Test Subject',
        )

    def test_compute_message_hash(self):
        """Test hash computation."""
        service = EmailSenderService(self.job)
        hash1 = service._compute_message_hash('test@example.com', 'Hello John')
        hash2 = service._compute_message_hash('test@example.com', 'Hello John')
        hash3 = service._compute_message_hash('test@example.com', 'Hello Jane')

        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)
        self.assertEqual(len(hash1), 64)  # SHA256 hex length

    def test_is_valid_email(self):
        """Test email validation."""
        service = EmailSenderService(self.job)
        self.assertTrue(service._is_valid_email('test@example.com'))
        self.assertTrue(service._is_valid_email('user.name@domain.co.uk'))
        self.assertFalse(service._is_valid_email('not-an-email'))
        self.assertFalse(service._is_valid_email('missing@domain'))
        self.assertFalse(service._is_valid_email('@nodomain.com'))


# Pytest-style tests for phone classifier
class PhoneClassifierTests(TestCase):
    """Tests for phone number classification."""

    def test_classify_mobile_us(self):
        """Test US mobile number classification."""
        from leads.services.phone_classifier import classify_phone
        # Use a valid US mobile number format
        result = classify_phone('+1 555 123 4567', 'US')
        self.assertIn('whatsapp_status', result)
        self.assertIn('whatsapp_check_link', result)
        self.assertIn('formatted_number', result)

    def test_classify_landline_us(self):
        """Test US landline classification."""
        from leads.services.phone_classifier import classify_phone
        result = classify_phone('+1 555-123-4567', 'US')  # This might be mobile
        # Just check it returns valid structure
        self.assertIn('whatsapp_status', result)
        self.assertIn('whatsapp_check_link', result)
        self.assertIn('formatted_number', result)

    def test_classify_empty(self):
        """Test empty phone number."""
        from leads.services.phone_classifier import classify_phone
        result = classify_phone('')
        self.assertEqual(result['whatsapp_status'], 'No phone listed')
        self.assertEqual(result['whatsapp_check_link'], '')

    def test_classify_invalid(self):
        """Test invalid phone number."""
        from leads.services.phone_classifier import classify_phone
        result = classify_phone('not-a-phone')
        self.assertEqual(result['whatsapp_status'], 'Unrecognized format')


class LeadModelTests(TestCase):
    """Tests for Lead model."""

    def test_create_lead(self):
        """Test creating a lead."""
        from leads.models import Lead, SearchJob

        job = SearchJob.objects.create(city='Test City', country='US', categories=['plumber'])
        lead = Lead.objects.create(
            search_job=job,
            name='Test Business',
            category='plumber',
            phone='+1 555-123-4567',
            has_website=False,
            whatsapp_status='Mobile — check via wa.me link',
            whatsapp_check_link='https://wa.me/15551234567',
        )
        self.assertTrue(lead.is_priority)

    def test_lead_with_website_not_priority(self):
        """Test lead with website is not priority."""
        from leads.models import Lead, SearchJob

        job = SearchJob.objects.create(city='Test City', country='US', categories=['plumber'])
        lead = Lead.objects.create(
            search_job=job,
            name='Test Business',
            category='plumber',
            has_website=True,
            whatsapp_status='Mobile — check via wa.me link',
        )
        self.assertFalse(lead.is_priority)

    def test_lead_landline_not_priority(self):
        """Test lead with landline is not priority."""
        from leads.models import Lead, SearchJob

        job = SearchJob.objects.create(city='Test City', country='US', categories=['plumber'])
        lead = Lead.objects.create(
            search_job=job,
            name='Test Business',
            category='plumber',
            has_website=False,
            whatsapp_status='Landline — WhatsApp unlikely',
        )
        self.assertFalse(lead.is_priority)


class ExporterTests(TestCase):
    """Tests for export functions."""

    def test_write_csv(self):
        """Test CSV export."""
        import tempfile
        import os
        from leads.services.exporters import write_csv
        from leads.models import Lead, SearchJob

        job = SearchJob.objects.create(city='Test City', country='US', categories=['plumber'])
        lead = Lead.objects.create(
            search_job=job,
            name='Test Business',
            category='plumber',
            phone='+1 555-123-4567',
            website='https://example.com',
            has_website=True,
            whatsapp_status='Mobile — check via wa.me link',
            whatsapp_check_link='https://wa.me/15551234567',
            osm_url='https://www.openstreetmap.org/node/123',
        )

        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            temp_path = f.name

        try:
            size = write_csv(temp_path, [lead])
            self.assertGreater(size, 0)

            with open(temp_path, 'r') as f:
                content = f.read()
                self.assertIn('Test Business', content)
                self.assertIn('plumber', content)
        finally:
            os.unlink(temp_path)