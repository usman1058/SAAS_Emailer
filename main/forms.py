import os
from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError



ALLOWED_EXCEL_EXTENSIONS = ['xlsx', 'xls']
ALLOWED_ATTACHMENT_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'txt', 'csv']
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_file_size(value):
    if value.size > MAX_FILE_SIZE:
        raise ValidationError(f'File size must be under {MAX_FILE_SIZE / (1024*1024)} MB.')


def validate_excel_file(value):
    ext = os.path.splitext(value.name)[1].lower().lstrip('.')
    if ext not in ALLOWED_EXCEL_EXTENSIONS:
        raise ValidationError(f'Only Excel files ({", ".join(ALLOWED_EXCEL_EXTENSIONS)}) are allowed.')


def validate_attachment_file(value):
    ext = os.path.splitext(value.name)[1].lower().lstrip('.')
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError(
            f'Attachment type not allowed. Allowed: {", ".join(ALLOWED_ATTACHMENT_EXTENSIONS)}'
        )


class EmailForm(forms.Form):
    sender_email = forms.EmailField(
        label='Sender Email',
        help_text='Your Gmail address (e.g., yourname@gmail.com)',
        validators=[validate_email],
    )
    sender_password = forms.CharField(
        label='Sender Password',
        widget=forms.PasswordInput(render_value=False),
        help_text='Gmail App Password (not your regular password)',
        strip=False,
    )
    subject = forms.CharField(
        label='Subject',
        max_length=255,
        help_text='Email subject line',
    )
    message = forms.CharField(
        label='Message',
        widget=forms.Textarea(attrs={'rows': 6}),
        help_text='Use {{name}} placeholder for personalization (e.g., "Hi {{name}}, ...")',
    )
    excel_file = forms.FileField(
        label='Excel File',
        help_text='Excel file with "Email" column (required) and optional "Name" column',
        validators=[validate_file_size, validate_excel_file],
    )
    attachment = forms.FileField(
        label='Attachment (optional)',
        required=False,
        help_text=f'Optional attachment. Allowed: {", ".join(ALLOWED_ATTACHMENT_EXTENSIONS)}. Max 10 MB.',
        validators=[validate_file_size, validate_attachment_file],
    )

    def clean_excel_file(self):
        excel_file = self.cleaned_data.get('excel_file')
        if excel_file:
            validate_excel_file(excel_file)
            validate_file_size(excel_file)
        return excel_file

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            validate_attachment_file(attachment)
            validate_file_size(attachment)
        return attachment