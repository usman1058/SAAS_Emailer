from django.urls import path
from .views import *

urlpatterns = [
    path('', email_panel, name='email_panel'),
    path('send_emails/', send_emails, name='send_emails'),
    path('stop/', stop_sending, name='stop_sending'),
]