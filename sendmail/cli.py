import logging
import pandas as pd
import typer
from pathlib import Path
from typing import Dict
import jinja2
from typing import Optional
import mailbox
import sendmail.util as utils


# ---------------------------------------------------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------------------------------------------------
app = typer.Typer()


# ---------------------------------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------------------------------
@app.command()
def sendmail(
    proj_dir: Optional[Path] = typer.Option(
        Path("."),
        "--dir",
        help="The directory containing project resources: a CSV file with email data and a template file",
    ),
    from_email: Optional[str] = typer.Option(
        None,
        "--from",
        help="Send all emails from this address. Overrides the 'from_email' column in the CSV file.",
    ),
    bcc_email: Optional[str] = typer.Option(
        None,
        "--bcc",
        help="BCC all emails to this address. Overrides the 'bcc_email' column in the CSV file.",
    ),
    force: Optional[bool] = typer.Option(
        False,
        "--force",
        help="Force send email to recipient even if an identical email has already been sent",
    ),
    yes: Optional[bool] = typer.Option(
        False,
        "--yes",
        help="Skip confirmation prompt",
    ),
    test: Optional[bool] = typer.Option(
        False,
        "--test",
        help="Test run using debug server. Copies of emails sent are saved to an mbox-test file in the proj directory.",
    ),
):
    """
    Send emails to recipients using data from a CSV file and an email template file.

    The CSV file must contain a column named 'to_email' and may also contain columns named 'from_email' and 'bcc_email'.
    All other columns will be passed to the template. If a 'from_mail' column is not present,
    the --from option must be used.

    The template file must contain a <subject> tag and a <text> tag. The <text> tag will be used as the plain text
    version of the email, and the <subject> tag will be used as the subject line.
    The template file may optionally contain an <html> tag. If present, the <html> tag will be used
    as the HTML version of the email.

    By default, the program will not send emails to recipients who have already received an identical email.
    You can override this behavior with the --force option.

    If a 'send_date' column is present in the CSV file, the program will only send emails to recipients
    whose send_date is in the past. This can be used to schedule emails to be sent at a later date.
    You can override this behavior with the --force option.

    There is a --test option that will simulate sending emails and create an mbox-test file in the
    project directory. This file can be opened with an email client to view the emails that would have been sent. It
    is a plain text file that may also be opened with a text editor.\n\n

    Example usage:\n\n

    # basic usage, to be run inside project directory:\n
    sendmail\n\n

    # run in test mode:\n
    sendmail --test\n\n

    # get this help message:\n
    sendmail --help\n\n

    # specify from address and bcc address on command line:\n
    sendmail --from expadmin@kellogg.northwestern.edu --bcc expadmin@kellogg.northwestern.edu
    """

    # data file for bulk email sending
    data_file = proj_dir / f"email-data.csv"
    assert data_file.exists(), f"File {data_file} does not exist."
    email_data = pd.read_csv(data_file)
    if from_email:
        email_data["from_email"] = from_email
    if bcc_email:
        email_data["bcc_email"] = bcc_email
    if "send_date" not in email_data.columns:
        email_data["send_date"] = pd.to_datetime("today")
    else:
        email_data["send_date"] = pd.to_datetime(email_data["send_date"])
    required_columns = ["to_email", "from_email", "send_date"]
    for col in required_columns:
        assert col in email_data.columns, f"File {data_file} does not contain a column named '{col}'."

    # template file for bulk email sending
    template_file = proj_dir / "email-template.jinja2"
    assert template_file.exists(), f"File {template_file} does not exist."
    env = jinja2.Environment(undefined=utils.Undefined)
    template = env.from_string(template_file.read_text())

    # create the mbox file
    mbox_name = "mbox-test" if test else "mbox"
    box = mailbox.mbox(proj_dir / mbox_name)

    # set up logging
    logfile_name = "sendmail-test.log" if test else "sendmail.log"
    logging.basicConfig(
        filename=str(proj_dir / logfile_name),
        encoding="utf-8",
        format="%(asctime)s : %(levelname)s : %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
        level=logging.INFO,
    )

    # make sure we really want to do this
    if not yes:
        really = typer.confirm(
            f"Are you sure you want to send {len(email_data)} emails?",
        )
        if not really:
            raise typer.Abort()

    # set up the smtp server
    smtp_server = "localhost"
    port = 25
    if test:
        debug_server_process = utils.start_debug_server(port=8025)
        port = debug_server_process.args[-1].split(":")[-1]

    # send the emails
    try:
        utils.send_emails(
            email_data=email_data,
            template=template,
            smtp_server=smtp_server,
            port=port,
            mbox=box,
            force=force,
        )
    except Exception as e:
        error = f"Error sending emails: {e}"
        console.print(f"[red]{error}")
        logging.error(error)
    finally:
        box.close()
        if test:
            debug_server_process.kill()
