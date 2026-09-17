"""
Leads App Views

Web interface for searching and viewing leads.
"""
import logging
import os
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import SearchJob, Lead, ExportFile
from .services.osm_client import OSMClient
from .services.phone_classifier import classify_phone, get_region_for_country
from .services.exporters import export_job_results

logger = logging.getLogger(__name__)


def lead_search(request):
    """Display search form and recent jobs."""
    recent_jobs = SearchJob.objects.all()[:20]
    popular_categories = [
        'plumber', 'electrician', 'cafe', 'hair salon', 'restaurant',
        'dentist', 'lawyer', 'gym', 'car repair', 'real estate agent',
        'accountant', 'doctor', 'vet', 'pharmacy', 'bakery'
    ]
    return render(request, 'leads/search.html', {
        'recent_jobs': recent_jobs,
        'popular_categories': popular_categories
    })


@require_POST
def lead_search_submit(request):
    """Handle search form submission and start background search."""
    city = request.POST.get('city', '').strip()
    country = request.POST.get('country', '').strip()
    categories_raw = request.POST.get('categories', '').strip()

    if not city or not categories_raw:
        messages.error(request, "City and at least one category are required.")
        return redirect('lead_search')

    categories = [c.strip() for c in categories_raw.split(',') if c.strip()]

    # Create job
    job = SearchJob.objects.create(
        city=city,
        country=country,
        categories=categories,
        status='pending',
    )

    # In production, this would be a Celery task
    # For now, run synchronously (with a warning for large searches)
    if len(categories) > 3:
        messages.warning(
            request,
            "Large searches may take a while. Consider using the management command for production use."
        )

    return redirect('lead_search_run', job_id=job.id)


def lead_search_run(request, job_id):
    """Run the search (synchronously) and show progress."""
    job = get_object_or_404(SearchJob, id=job_id)

    if job.status == 'running':
        messages.info(request, "Search is already running.")
        return redirect('lead_results', job_id=job.id)

    if job.status == 'completed':
        messages.info(request, "Search already completed.")
        return redirect('lead_results', job_id=job.id)

    # Run search
    job.status = 'running'
    job.started_at = timezone.now()
    job.save(update_fields=['status', 'started_at'])

    try:
        client = OSMClient()
        bbox = client.geocode_city(job.city, job.country)

        region = get_region_for_country(job.country)
        seen_ids = set()
        all_leads = []

        for category in job.categories:
            results = client.search_category(bbox, category)
            for parsed in results:
                if parsed["osm_id"] in seen_ids:
                    continue
                seen_ids.add(parsed["osm_id"])

                phone_info = classify_phone(parsed["phone"], region)

                all_leads.append(Lead(
                    search_job=job,
                    name=parsed["name"],
                    category=category.strip(),
                    address=parsed["address"] or f"{job.city} (exact address not mapped on OSM)",
                    phone=phone_info["formatted_number"] or parsed["phone"],
                    website=parsed["website"],
                    has_website=bool(parsed["website"]),
                    whatsapp_status=phone_info["whatsapp_status"],
                    whatsapp_check_link=phone_info["whatsapp_check_link"],
                    osm_url=f"https://www.openstreetmap.org/{parsed['osm_id']}",
                ))

        if all_leads:
            Lead.objects.bulk_create(all_leads)

        job.total_found = len(all_leads)
        job.no_website_count = sum(1 for lead in all_leads if not lead.has_website)
        job.priority_count = sum(1 for lead in all_leads if lead.is_priority)
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save(update_fields=[
            'total_found', 'no_website_count', 'priority_count',
            'status', 'completed_at'
        ])

        messages.success(request, f"Search completed! Found {len(all_leads)} businesses.")

    except Exception as e:
        job.status = 'failed'
        job.error_message = str(e)
        job.save(update_fields=['status', 'error_message'])
        logger.exception("Lead search failed")
        messages.error(request, f"Search failed: {e}")

    return redirect('lead_results', job_id=job.id)


def lead_results(request, job_id):
    """Display search results with filters and pagination."""
    job = get_object_or_404(SearchJob, id=job_id)

    # Get filter parameters
    website_filter = request.GET.get('website', '')  # 'yes', 'no', or ''
    whatsapp_filter = request.GET.get('whatsapp', '')  # 'mobile', or ''

    leads_qs = job.leads.all()

    if website_filter == 'yes':
        leads_qs = leads_qs.filter(has_website=True)
    elif website_filter == 'no':
        leads_qs = leads_qs.filter(has_website=False)

    if whatsapp_filter == 'mobile':
        leads_qs = leads_qs.filter(whatsapp_status__startswith='Mobile')

    # Pagination
    paginator = Paginator(leads_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'job': job,
        'page_obj': page_obj,
        'website_filter': website_filter,
        'whatsapp_filter': whatsapp_filter,
        'total_count': job.total_found,
        'no_website_count': job.no_website_count,
        'priority_count': job.priority_count,
    }
    return render(request, 'leads/results.html', context)


def lead_export(request, job_id, fmt):
    """Export search results."""
    job = get_object_or_404(SearchJob, id=job_id)

    if job.status != 'completed':
        messages.error(request, "Job not completed yet.")
        return redirect('lead_results', job_id=job.id)

    output_dir = os.path.join(settings.MEDIA_ROOT, 'leads_exports')
    os.makedirs(output_dir, exist_ok=True)

    base_name = f"leads_{job.city.lower().replace(' ', '_')}_{job.id}"
    export_job_results(job, output_dir, base_name)

    # Map format to file
    file_map = {
        'csv': f"{base_name}_all.csv",
        'csv_no_website': f"{base_name}_no_website.csv",
        'csv_priority': f"{base_name}_priority.csv",
        'xlsx': f"{base_name}.xlsx",
        'html': f"{base_name}_report.html",
    }

    if fmt not in file_map:
        raise Http404("Invalid export format")

    file_path = os.path.join(output_dir, file_map[fmt])
    if not os.path.exists(file_path):
        messages.error(request, "Export file not found. Please try again.")
        return redirect('lead_results', job_id=job.id)

    # Record export
    ExportFile.objects.create(
        search_job=job,
        file_format=fmt,
        file_path=file_path,
        file_size=os.path.getsize(file_path),
    )

    return FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename=file_map[fmt]
    )


def lead_job_status(request, job_id):
    """AJAX endpoint for job status."""
    job = get_object_or_404(SearchJob, id=job_id)
    return JsonResponse({
        'id': job.id,
        'status': job.status,
        'total_found': job.total_found,
        'no_website_count': job.no_website_count,
        'priority_count': job.priority_count,
        'is_active': job.is_active,
        'error_message': job.error_message,
    })


def import_to_email_sender(request, job_id):
    """Get emails from priority leads for email sender."""
    get_object_or_404(SearchJob, id=job_id)

    # We don't have email addresses from OSM, but we can export names/phones
    # This would need manual email collection or a different approach

    # For now, redirect to email panel with a message
    messages.info(
        request,
        "OSM data doesn't include email addresses. Use the exported leads to "
        "manually find contact emails, then use the Email Sender."
    )
    return redirect('email_panel')