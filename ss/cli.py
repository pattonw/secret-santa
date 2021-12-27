import click

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from omegaconf import OmegaConf

from .assignment import assignment, emails
from .store import store_assignments, read_assignments
from .emails import send_email


@click.group()
@click.option("-c", "--config", type=str, required=True)
@click.pass_context
def cli(ctx, config):
    ctx.ensure_object(dict)
    c = OmegaConf.load(f"configs/{config}/config.yaml")
    ctx.obj["config"] = c
    ctx.obj["directory"] = f"configs/{config}"


@cli.command()
@click.option("--real/--test", default=False)
@click.pass_context
def assignments(ctx, real):
    c = ctx.obj["config"]

    participant_emails = emails(c)
    history = read_assignments(ctx.obj["directory"])
    assignments = list(assignment(c, history))
    store_assignments(ctx.obj["directory"], assignments)

    for gifter, giftee in assignments:
        gifter, giftee = gifter.capitalize(), giftee.capitalize()

        header = open(f"{ctx.obj['directory']}/email_header.txt").read()
        content = (
            open(f"{ctx.obj['directory']}/content.txt")
            .read()
            .format(gifter=gifter, giftee=giftee, gifter_upper=gifter.upper())
        )
        footer = open(f"{ctx.obj['directory']}/email_footer.txt").read()

        html = header + content + footer

        message = MIMEMultipart("alternative")
        message["Subject"] = c.subject.format(gifter=gifter)
        message["From"] = c.sender
        if real:
            message["To"] = participant_emails[gifter.lower()]
        else:
            message["To"] = c.sender

        # part1 = MIMEText(content, "plain")
        part2 = MIMEText(html, "html")

        # Add HTML/plain-text parts to MIMEMultipart message
        # The email client will try to render the last part first
        # message.attach(part1)
        message.attach(part2)

        if real:
            send_email(c.sender, participant_emails[gifter.lower()], c.password, message)
        else:
            print(gifter, giftee)
