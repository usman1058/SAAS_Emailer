from django import forms

class EmailForm(forms.Form):
    sender_email = forms.EmailField()
    sender_password = forms.CharField(widget=forms.PasswordInput)
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)
    excel_file = forms.FileField()
    attachment = forms.FileField(required=False)
