"""Tests for `mturkhelper` package."""

import os
import shutil
import pandas as pd
import pytest
from pathlib import Path
from typer.testing import CliRunner
from sendmail.cli import app
from jinja2 import Template
import sendmail.util as utils
import time
import mailbox


dir_path = Path(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def email_data_path():
    path = dir_path / "data/sendmail/email-data.csv"
    path.exists()
    return path


@pytest.fixture(scope="session")
def email_template_path():
    path = dir_path / "data/sendmail/email-template.jinja2"
    path.exists()
    return path


# @pytest.mark.skip("not implemented")
def test_command_line_interface(email_data_path, email_template_path, tmp_path):
    shutil.copyfile(email_data_path, tmp_path / "email-data.csv")
    assert (tmp_path / "email-data.csv").exists()
    shutil.copyfile(email_template_path, tmp_path / "email-template.jinja2")
    assert (tmp_path / "email-template.jinja2").exists()
    runner = CliRunner()
    result = runner.invoke(app, ["--dir", str(tmp_path), "--test", "--yes"])
    print(result.stdout)
    assert result.exit_code == 0


@pytest.mark.parametrize("row_num", [0, 1, 2])
def test_create_message(email_data_path, email_template_path, row_num):
    email_data = pd.read_csv(email_data_path)
    email_data = email_data.to_dict(orient="records")
    template = Template(email_template_path.read_text())
    message = utils.create_message(template, email_data[row_num])
    assert message["From"] == "wkt@northwestern.edu"
    assert message["To"] == email_data[row_num]["to_email"]
    assert message["Subject"] == f"Invitation to the Test{row_num+1} study"
    payloads = [p for p in message.get_payload()]
    assert len(payloads) == 2
    assert payloads[0].get_content_type() == "text/plain"
    assert payloads[1].get_content_type() == "text/html"


def test_send_emails(email_data_path, email_template_path, smtp_server, tmp_path):
    email_data = pd.read_csv(email_data_path)
    template = Template(email_template_path.read_text())
    mbox_dir = tmp_path / "mbox"
    mbox_dir.mkdir(parents=True)
    mbox = mailbox.mbox(mbox_dir / "test.mbox")
    time.sleep(2)
    utils.send_emails(
        email_data=email_data,
        template=template,
        smtp_server="localhost",
        port=8025,
        mbox=mbox,
        force=False,
    )
    assert len(mbox) == 2
    utils.send_emails(
        email_data=email_data,
        template=template,
        smtp_server="localhost",
        port=8025,
        mbox=mbox,
        force=False,
    )
    assert len(mbox) == 2
    utils.send_emails(
        email_data=email_data,
        template=template,
        smtp_server="localhost",
        port=8025,
        mbox=mbox,
        force=True,
    )
    assert len(mbox) == 6
