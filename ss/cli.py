from .assignment import assignment, emails
from .store import store_assignments, read_assignments
from .emails import send_email

import click

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from omegaconf import OmegaConf

from pathlib import Path
from pprint import pprint


@click.group()
@click.argument("config-dir", type=click.Path(exists=True))
@click.pass_context
def cli(ctx, config_dir):
    """
    CONFIG-DIR is the directory containing the configs for your secret santa assignments.
    """
    config_dir = Path(config_dir)
    ctx.ensure_object(dict)
    c = OmegaConf.load(config_dir / "config.yaml")
    ctx.obj["config"] = c
    ctx.obj["directory"] = config_dir


@cli.command()
@click.pass_context
def print_history(ctx):
    """
    print history of annual assignments made
    """
    historical_assignments = {
        k: {v1: v2 for v1, v2 in v}
        for k, v in read_assignments(ctx.obj["directory"], history=True).items()
    }
    pprint("Historical assignments:")
    pprint(historical_assignments)


@cli.command()
@click.pass_context
def print_assignments(ctx):
    """
    print current assignments
    """
    historical_assignments = {
        a: b for a, b in read_assignments(ctx.obj["directory"], history=False)
    }
    pprint("Assignments:")
    pprint(historical_assignments)


@cli.command()
@click.option(
    "--save/--test",
    default=False,
    help="Whether to save the results of this assignment. "
    "If true assignments will be saved to history file. "
    "If false assignments will be printed to terminal.",
)
@click.pass_context
def new_assignments(ctx, save):
    """
    create new assignments
    """
    c = ctx.obj["config"]

    history = read_assignments(ctx.obj["directory"], history=True)
    assignments = list(assignment(c, history))
    if save:
        store_assignments(ctx.obj["directory"], assignments)
    else:
        print("Assignments:")
        pprint({a: b for a, b in assignments})


@cli.command()
@click.option(
    "--real/--test",
    default=False,
    help="Whether to send assignments to participants or run a test. "
    "If False will send an email to the organizer with each participants name and email. "
    "If True will send assignments to each participant.",
)
@click.pass_context
def email(ctx, real):
    """
    send out emails with assignments
    """
    c = ctx.obj["config"]

    participant_emails = emails(c)
    assignments = read_assignments(ctx.obj["directory"], history=False)

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
            send_email(
                c.sender, participant_emails[gifter.lower()], c.password, message
            )
        else:
            print(gifter, giftee)
