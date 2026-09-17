"""
Django Management Command: find_leads

Finds local businesses without websites using OpenStreetMap data.
"""
import logging
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from leads.models import Lead, SearchJob
from leads.services.osm_client import OSMClient
from leads.services.phone_classifier import classify_phone, get_region_for_country
from leads.services.exporters import export_job_results

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Find local businesses without websites using OpenStreetMap data."

    def add_arguments(self, parser):
        parser.add_argument("--city", required=True, help="City name (e.g., 'Leeds')")
        parser.add_argument("--country", default="", help="Country name (e.g., 'UK')")
        parser.add_argument(
            "--categories",
            nargs="+",
            required=True,
            help="Business categories to search (e.g., plumber electrician cafe)",
        )
        parser.add_argument(
            "--output",
            default="leads",
            help="Base name for output files (default: leads)",
        )
        parser.add_argument(
            "--email",
            default="",
            help="Contact email for OSM API (recommended for heavy usage)",
        )

    def handle(self, *args, **options):
        city = options["city"]
        country = options["country"]
        categories = options["categories"]
        output_base = options["output"]
        contact_email = options["email"]

        self.stdout.write(f"Starting lead search for {city}" + (f", {country}" if country else ""))

        # Create search job record
        job = SearchJob.objects.create(
            city=city,
            country=country,
            categories=categories,
            status='running',
        )

        try:
            client = OSMClient(contact_email=contact_email)

            # Geocode city
            self.stdout.write(f"Geocoding '{city}'...")
            bbox = client.geocode_city(city, country)
            time.sleep(1)  # Be polite to Nominatim

            region = get_region_for_country(country)

            seen_ids = set()
            all_leads = []

            for category in categories:
                self.stdout.write(f"Searching Overpass for: {category}")
                results = client.search_category(bbox, category)
                self.stdout.write(f"  {len(results)} raw OSM elements returned")

                for parsed in results:
                    if parsed["osm_id"] in seen_ids:
                        continue
                    seen_ids.add(parsed["osm_id"])

                    phone_info = classify_phone(parsed["phone"], region)

                    lead = Lead(
                        search_job=job,
                        name=parsed["name"],
                        category=category.strip(),
                        address=parsed["address"] or f"{city} (exact address not mapped on OSM)",
                        phone=phone_info["formatted_number"] or parsed["phone"],
                        website=parsed["website"],
                        has_website=bool(parsed["website"]),
                        whatsapp_status=phone_info["whatsapp_status"],
                        whatsapp_check_link=phone_info["whatsapp_check_link"],
                        osm_url=f"https://www.openstreetmap.org/{parsed['osm_id']}",
                    )
                    all_leads.append(lead)

                time.sleep(2)  # Be polite to Overpass

            # Bulk create leads
            if all_leads:
                Lead.objects.bulk_create(all_leads)

            # Update job stats
            job.total_found = len(all_leads)
            job.no_website_count = sum(1 for lead in all_leads if not lead.has_website)
            job.priority_count = sum(1 for lead in all_leads if lead.is_priority)
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.save()

            # Export files
            output_dir = os.path.join(settings.MEDIA_ROOT, 'leads_exports')
            os.makedirs(output_dir, exist_ok=True)

            export_results = export_job_results(job, output_dir, output_base)

            self.stdout.write(self.style.SUCCESS(f"\nDone. {len(all_leads)} businesses total."))
            self.stdout.write(f"  {job.no_website_count} have no website")
            self.stdout.write(f"  {job.priority_count} have no website AND a mobile number (best leads)")
            self.stdout.write(f"\nFiles written to {output_dir}:")
            for fmt, size in export_results.items():
                self.stdout.write(f"  {fmt}: {size} bytes")

        except Exception as e:
            job.status = 'failed'
            job.error_message = str(e)
            job.save()
            logger.exception("Lead search failed")
            raise CommandError(f"Lead search failed: {e}")