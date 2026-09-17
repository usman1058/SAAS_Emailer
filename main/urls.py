from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('email/', views.email_panel, name='email_panel'),
    path('send_emails/', views.send_emails, name='send_emails'),
    path('stop/<int:job_id>/', views.stop_sending, name='stop_sending'),
    path('job_status/<int:job_id>/', views.job_status, name='job_status'),
]