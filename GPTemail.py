import os
import imaplib
import smtplib
import json
import time
import mimetypes
import base64
import openai
from datetime import datetime
from email import message_from_bytes
from email.message import EmailMessage
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from docx import Document

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
WHITELIST = ['youremail@example.com'] # replace with your own email
CONVO_FILE = 'conversation_store.json'

openai.api_key = OPENAI_API_KEY

def log(message):
    # timestamps lol
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def load_conversations():
    # loads conversation history from json, if it doesnt exist then return empty dict
    if not os.path.exists(CONVO_FILE):
        return {}
    with open(CONVO_FILE, 'r') as f:
        return json.load(f)

def save_conversations(convos):
    # saves conversations
    with open(CONVO_FILE, 'w') as f:
        json.dump(convos, f, indent=2)

def extract_text_attachment(part):
    # this whole function just reads text from files
    filename = part.get_filename()
    ext = os.path.splitext(filename)[-1].lower()
    content = part.get_payload(decode=True)

    if ext == '.txt':
        return filename, content.decode(errors='ignore')
    elif ext == '.pdf':
        with open('temp.pdf', 'wb') as f:
            f.write(content)
        reader = PdfReader('temp.pdf')
        text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        os.remove('temp.pdf')
        return filename, text
    elif ext == '.docx':
        with open('temp.docx', 'wb') as f:
            f.write(content)
        doc = Document('temp.docx')
        text = "\n".join([p.text for p in doc.paragraphs])
        os.remove('temp.docx')
        return filename, text
    return filename, None

def extract_image_base64(part):
    # converts images to base64 so GPT can see it
    filename = part.get_filename()
    if not filename:
        return None, None

    ext = os.path.splitext(filename)[1]
    mime_type = mimetypes.types_map.get(ext, 'image/png')
    content = part.get_payload(decode=True)
    b64 = base64.b64encode(content).decode()
    data_url = f"data:{mime_type};base64,{b64}"
    return filename, data_url

def fetch_email():
    # connects to the email service (gmail)
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")

    result, data = mail.search(None, "(UNSEEN)")
    mail_ids = data[0].split()

    for mail_id in mail_ids:
        result, msg_data = mail.fetch(mail_id, "(RFC822)")
        raw_email = msg_data[0][1]
        message = message_from_bytes(raw_email)

        sender = message['From'].split('<')[-1].replace('>', '').strip()
        subject = message['Subject'] or ''
        if sender not in WHITELIST:
            log(f"Ignored email from non whitelisted user: {sender}")
            continue

        body = ""
        attachments = []
        images = []

        if message.is_multipart():
            # check if email has multiple parts
            for part in message.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition"))

                if ctype == "text/plain" and "attachment" not in disp:
                    body = part.get_payload(decode=True).decode()
                elif "attachment" in disp:
                    fname = part.get_filename()
                    if fname:
                        ext = os.path.splitext(fname)[-1].lower()
                        if ext in ['.pdf', '.txt', '.docx']:
                            fname, text = extract_text_attachment(part)
                            if text:
                                attachments.append((fname, text))
                        elif ext in ['.png', '.jpg', '.jpeg', '.webp']:
                            fname, img = extract_image_base64(part)
                            if img:
                                images.append(img)
        else:
            body = message.get_payload(decode=True).decode()

        return sender, subject, body.strip(), attachments, images

    return None, None, None, [], []

def build_message_content(prompt_text, attachments, image_data_urls):
    # build message array for GPT
    messages = [{"type": "text", "text": prompt_text}]

    for fname, content in attachments:
        # add any text attachments to the message
        messages.append({
            "type": "text",
            "text": f"[Attached File: {fname}]\n{content[:3000]}{'...' if len(content) > 3000 else ''}"
        })
    # add images if there are any
    for img_url in image_data_urls:
        messages.append({
            "type": "image_url",
            "image_url": {"url": img_url}
        })

    return messages

def get_chat_response(sender, prompt, subject, attachments, images, conversations):
    is_new = 'new' in subject.lower()
    user_convo = conversations.get(sender, [])

    message_content = build_message_content(prompt, attachments, images)

    if is_new or not user_convo:
        convo = [{"role": "user", "content": message_content}]
    else:
        convo = user_convo
        convo.append({"role": "user", "content": message_content})

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=convo
    )

    reply = response.choices[0].message.content.strip()
    convo.append({"role": "assistant", "content": reply})
    conversations[sender] = convo
    return reply, conversations

def send_reply(to_email, subject, body):
    # reply back to the user
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = 'Re: ' + subject
    msg['From'] = EMAIL_USER
    msg['To'] = to_email

    with smtplib.SMTP_SSL(SMTP_SERVER, 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

def main_loop():
    # main loop that runs forever
    while True:
        try:
            sender, subject, body, attachments, images = fetch_email()
            if sender and body:
                log(f"Received email from {sender} | Subject: {subject}")
                conversations = load_conversations()
                reply, conversations = get_chat_response(sender, body, subject, attachments, images, conversations)
                save_conversations(conversations)
                send_reply(sender, subject, reply)
                log(f"Sent reply to {sender}")
        except Exception as e:
            # catch errors so the script doesnt crap itself (crash)
            log(f"[ERROR] {e}")
        time.sleep(5) # wait

if __name__ == '__main__':
    log("GPTemail started")
    main_loop() # start GPTemail
