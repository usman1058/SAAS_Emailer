from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('', views.lead_search, name='search'),
    path('submit/', views.lead_search_submit, name='search_submit'),
    path('run/<int:job_id>/', views.lead_search_run, name='search_run'),
    path('results/<int:job_id>/', views.lead_results, name='results'),
    path('export/<int:job_id>/<str:fmt>/', views.lead_export, name='export'),
    path('status/<int:job_id>/', views.lead_job_status, name='job_status'),
    path('import/<int:job_id>/', views.import_to_email_sender, name='import_to_email'),
]