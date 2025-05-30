import os
import re
import time
import hashlib
import pandas as pd
import smtplib
from email.message import EmailMessage
import mimetypes
from django.shortcuts import render, redirect
from .forms import EmailForm
from django.core.files.storage import FileSystemStorage
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

is_sending = False  # Kill switch flag

def email_panel(request):
    form = EmailForm()
    return render(request, 'send_emails.html', {'form': form})

@csrf_exempt
def stop_sending(request):
    global is_sending
    is_sending = False
    return redirect('email_panel')

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)





def send_emails(request):
    global is_sending
    if request.method == 'POST':
        form = EmailForm(request.POST, request.FILES)
        if form.is_valid():
            sender_email = form.cleaned_data['sender_email']
            sender_password = form.cleaned_data['sender_password']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            excel_file = request.FILES['excel_file']
            attachment = request.FILES.get('attachment')

            fs = FileSystemStorage()
            excel_path = fs.save(excel_file.name, excel_file)
            attachment_path = fs.save(attachment.name, attachment) if attachment else None

            sent_folder = os.path.join(settings.MEDIA_ROOT, 'sent_emails')
            os.makedirs(sent_folder, exist_ok=True)
            sent_file_path = os.path.join(sent_folder, 'sent_hashes.txt')

            sent_hashes = set()
            if os.path.exists(sent_file_path):
                with open(sent_file_path, 'r') as f:
                    sent_hashes = set(line.strip() for line in f if line.strip())

            def stream():
                global is_sending
                is_sending = True
                yield "Starting email sending...\n"

                def connect_smtp():
                    try:
                        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                        server.login(sender_email, sender_password)
                        return server, None
                    except Exception as e:
                        return None, f"❌ Login failed: {e}\n"

                try:
                    df = pd.read_excel(fs.path(excel_path))
                    server, login_error = connect_smtp()
                    if login_error:
                        yield login_error
                        return

                    for i, (_, row) in enumerate(df.iterrows()):
                        if not is_sending:
                            yield "Stopped by user.\n"
                            break

                        recipient = str(row.get('Email')).strip() if row.get('Email') else None
                        if not recipient or not is_valid_email(recipient):
                            yield f"⚠️ Skipping invalid or missing email.\n"
                            continue

                        name = str(row.get('Name')).strip().split()[0] if row.get('Name') else "there"
                        personalized_message = message.replace("{{name}}", name)
                        msg_hash = hashlib.sha256((recipient + personalized_message).encode()).hexdigest()

                        if msg_hash in sent_hashes:
                            yield f"🔁 Skipping duplicate for {recipient}\n"
                            continue

                        msg = EmailMessage()
                        from email.utils import formataddr
                        msg['From'] = formataddr(("KenesisnTech", sender_email))
                        msg['To'] = recipient
                        msg['Subject'] = subject
                        msg.set_content(personalized_message)

                        if attachment_path:
                            mime_type, _ = mimetypes.guess_type(fs.path(attachment_path))
                            if mime_type:
                                main_type, sub_type = mime_type.split('/')
                                with open(fs.path(attachment_path), 'rb') as f:
                                    msg.add_attachment(
                                        f.read(), maintype=main_type, subtype=sub_type,
                                        filename=attachment.name
                                    )

                        try:
                            server.send_message(msg)
                            yield f"✅ Sent to {recipient}\n"
                            sent_hashes.add(msg_hash)
                            with open(sent_file_path, 'a') as f:
                                f.write(msg_hash + '\n')
                        except smtplib.SMTPServerDisconnected:
                            yield "⚠️ Connection lost. Reconnecting...\n"
                            server, reconnect_error = connect_smtp()
                            if reconnect_error:
                                yield reconnect_error
                                break
                            try:
                                server.send_message(msg)
                                yield f"✅ Sent to {recipient} after reconnect\n"
                                sent_hashes.add(msg_hash)
                                with open(sent_file_path, 'a') as f:
                                    f.write(msg_hash + '\n')
                            except Exception as e:
                                yield f"❌ Failed after reconnect: {str(e)}\n"
                                break
                        except Exception as e:
                            yield f"❌ Failed to send to {recipient}: {str(e)}\n"

                        time.sleep(0.5)

                        if (i + 1) % 20 == 0:
                            try:
                                server.quit()
                            except:
                                pass
                            server, reconnect_error = connect_smtp()
                            if reconnect_error:
                                yield reconnect_error
                                break

                    try:
                        server.quit()
                    except:
                        pass
                    yield "✅ Finished sending emails.\n"

                except Exception as e:
                    yield f"❌ Error: {str(e)}\n"

            return StreamingHttpResponse(stream(), content_type="text/plain")

    return redirect('email_panel')
