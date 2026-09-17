import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages

from .forms import EmailForm
from .models import SendJob
from .services.email_sender import EmailSenderService

logger = logging.getLogger(__name__)


def email_panel(request):
    """Render the email sending form."""
    form = EmailForm()
    recent_jobs = SendJob.objects.all()[:10]
    return render(request, 'send_emails.html', {'form': form, 'recent_jobs': recent_jobs})


@require_POST
def stop_sending(request, job_id):
    """Stop a running email job (kill switch)."""
    job = get_object_or_404(SendJob, id=job_id)
    if job.is_active:
        job.status = 'stopped'
        job.save(update_fields=['status'])
        messages.success(request, f"Job #{job_id} has been stopped.")
    else:
        messages.info(request, f"Job #{job_id} is not running.")
    return redirect('email_panel')


def send_emails(request):
    """Handle email sending form submission and stream progress."""
    if request.method == 'POST':
        form = EmailForm(request.POST, request.FILES)
        if form.is_valid():
            # Create job record
            job = SendJob.objects.create(
                sender_email=form.cleaned_data['sender_email'],
                subject=form.cleaned_data['subject'],
                status='pending',
            )

            sender_email = form.cleaned_data['sender_email']
            sender_password = form.cleaned_data['sender_password']
            subject = form.cleaned_data['subject']
            message_text = form.cleaned_data['message']
            excel_file = request.FILES['excel_file']
            attachment = request.FILES.get('attachment')

            # Create service and stream responses
            service = EmailSenderService(job)

            def stream():
                for log_message in service.send_emails(
                    sender_email=sender_email,
                    sender_password=sender_password,
                    subject=subject,
                    message_template=message_text,
                    excel_file=excel_file,
                    attachment=attachment,
                ):
                    yield log_message

            response = StreamingHttpResponse(stream(), content_type="text/plain")
            response['X-Job-ID'] = str(job.id)
            return response

    return redirect('email_panel')


def job_status(request, job_id):
    """Get job status for AJAX polling."""
    job = get_object_or_404(SendJob, id=job_id)
    return JsonResponse({
        'id': job.id,
        'status': job.status,
        'sent_count': job.sent_count,
        'failed_count': job.failed_count,
        'skipped_duplicates': job.skipped_duplicates,
        'skipped_invalid': job.skipped_invalid,
        'total_recipients': job.total_recipients,
        'progress_percent': job.progress_percent,
        'is_active': job.is_active,
    })