import logging
import socket
import pandas as pd
import smtplib
from typing import Dict
from rich.console import Console
import jinja2
import email
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import mailbox
import re
import time
import subprocess
from pathlib import Path
import datetime
import time


# ---------------------------------------------------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------------------------------------------------
console = Console(style="green on black")


class Undefined(jinja2.Undefined):
    def __init__(self, *args, **kwargs):
        super(Undefined, self).__init__(*args, **kwargs)
        self.name


# ---------------------------------------------------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------------------------------------------------
def create_message(template: jinja2.Template, record: Dict) -> email.message.Message:
    """
    Create an email.message.Message object from a jinja2.Template object and a record of data.
    :param template:
    :param record:
    :return: message - an email.message.Message object
    """
    subj_pat = re.compile(r"<subject>(.+)<\/subject>", re.DOTALL)
    text_pat = re.compile(r"<text>(.+)<\/text>", re.DOTALL)
    html_pat = re.compile(r"(<html>.+<\/html>)", re.DOTALL)

    try:
        rendered = template.render(record)
    except jinja2.exceptions.UndefinedError as e:
        error = f"[red]Error rendering template for record: {record}. Error: {e}."
        console.print(error)
        logging.error(error)
        return None
    subject = subj_pat.search(rendered).group(1).strip()
    text = text_pat.search(rendered).group(1).strip()
    if html_pat.search(rendered):
        html = html_pat.search(rendered).group(1).strip()
    else:
        html = None

    message = MIMEMultipart("alternative")
    message["From"] = record["from_email"]
    message["To"] = record["to_email"]
    if "bcc_email" in record:
        message["Bcc"] = record["bcc_email"]
    message["Subject"] = subject
    message.attach(MIMEText(text, "plain"))
    if html:
        message.attach(MIMEText(html, "html"))
        
    if 'attachments' in record:
        for file in record['attachments']:
            part = MIMEBase('application', "octet-stream")
            with open(file, 'rb') as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition',
                            'attachment; filename={}'.format(Path(file).name))
            message.attach(part)

    return message


def check_port(port) -> bool:
    """
    Check if a port is in use.
    :param port:
    :return:
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("localhost", port))
    if result == 0:
        return True
    return False


def hash_message(message: MIMEMultipart) -> int:
    """
    Hash an email.message.Message object.
    :param message:
    :return:
    """
    return hash(str(message["To"]) + str(message["From"]) + str(message["Subject"]) + "".join([str(p) for p in message.get_payload()]))


def start_debug_server(port: int = 8025) -> subprocess.Popen:
    """
    Start an aiosmtpd debug server on a port that is not in use.
    :param port:
    :return:
    """
    while port < 9000:
        if check_port(port):
            port += 1
        else:
            break
    console.print(f"Starting debug server on port: {port}")
    debug_server_process = subprocess.Popen(
        [
            "aiosmtpd",
            "-n",
            "-l",
            f"localhost:{port}",
        ]
    )
    time.sleep(2)
    return debug_server_process


def send_emails(
    email_data: pd.DataFrame,
    template: jinja2.Template,
    smtp_server: str,
    port: int,
    mbox: mailbox.mbox,
    force: bool,
    delay: int = 0
) -> None:
    """
    Send emails from a dataframe of email data and a jinja2.Template object.
    :param email_data:
    :param template:
    :param smtp_server:
    :param port:
    :param mbox:
    :param force:
    :param delay
    :return:
    """
    sent_messages = {hash_message(m): m for m in mbox}
    email_data["send_date_passed"] = email_data["send_date"] <= pd.to_datetime("today")
    records = email_data.to_dict(orient="records")
    with smtplib.SMTP(smtp_server, port) as server:
        for r in records:
            m = create_message(template, r)
            if not m:
                warning = "No message generated"
                console.print(f"[bold yellow]{warning}")
                logging.warning(warning)
                continue
            if hash_message(m) in sent_messages and not force:
                warning = f"Refusing to send duplicate email to address: {m['To']}"
                console.print(f"[bold yellow]{warning}")
                logging.warning(warning)
                continue
            if r["send_date_passed"] or force:
                mbox.add(m)
                mbox.flush()
                info = f"Sending message to: {m['To']}"
                console.print(f"[bold green]{info}")
                logging.info(info)
                server.send_message(m)
                if delay:
                    time.sleep(delay)
                sent_messages[hash_message(m)] = m
