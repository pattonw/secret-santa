from .assignment import assignment, emails
from .store import store_assignments, read_assignments, write_assignments, load
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
@click.option(
    "--decode/--raw",
    default=False,
    help="Whether to decode the secret string into readable text.",
)
@click.pass_context
def print_history(ctx, decode):
    """
    print history of annual assignments made
    """
    if decode:
        key = bytes((ctx.obj["directory"] / "config.yaml").open().read(), "utf-8")
    else:
        key = None
    historical_assignments = {
        k: {v1: v2 for v1, v2 in v}
        for k, v in read_assignments(ctx.obj["directory"], history=True, key=key).items()
    }
    pprint("Historical assignments:")
    pprint(historical_assignments)


@cli.command()
@click.argument(
    "year",
    type=int,
    # help="Which year to encode.",
)
@click.pass_context
def encode(ctx, year):
    """
    print history of annual assignments made
    """
    f_to_encode = ctx.obj["directory"] / "history"/ f"{year}.json"
    to_encode = load(f_to_encode)
    key = bytes((ctx.obj["directory"] / "config.yaml").open().read(), "utf-8")
    write_assignments(f_to_encode, to_encode, key)


@cli.command()
@click.option(
    "--decode/--raw",
    default=False,
    help="Whether to decode the secret string into readable text.",
)
@click.pass_context
def print_assignments(ctx, decode):
    """
    print current assignments
    """

    if decode:
        key = bytes((ctx.obj["directory"] / "config.yaml").open().read(), "utf-8")
    else:
        key = None

    historical_assignments = {
        a: b for a, b in read_assignments(ctx.obj["directory"], history=False, key=key)
    }
    pprint("Assignments:")
    pprint(historical_assignments)


@cli.command()
@click.option(
    "--encode/--decode",
    default=False,
    help="Whether to decode the secret string into readable text.",
)
@click.option(
    "-in",
    "--input-file",
    type=click.Path(exists=True, dir_okay=False),
    help="The file to encode or decode.",
)
@click.option(
    "-out",
    "--output-file",
    type=click.Path(exists=False),
    help="The file to save encoded or decoded data.",
)
@click.pass_context
def recode_assignments(ctx, encode, input_file, output_file):
    """
    Either decode and write decoded assignments to new file
    or encode and write encoded assignments to file
    """

    key = bytes((ctx.obj["directory"] / "config.yaml").open().read(), "utf-8")

    input_file = Path(input_file)
    output_file = Path(output_file)

    if encode:
        assignments = load(input_file, key=None)
        write_assignments(output_file, assignments, key=key)
    else:
        assignments = load(input_file, key=key)
        write_assignments(output_file, assignments, key=None)


@cli.command()
@click.option(
    "--save/--test",
    default=False,
    help="Whether to save the results of this assignment. "
    "If true assignments will be saved to history file. "
    "If false assignments will be printed to terminal.",
)
@click.option(
    "--encode/--raw",
    default=True,
    help="Whether to hash assignments to keep them secret. Even from you.",
)
@click.pass_context
def new_assignments(ctx, save, encode):
    """
    create new assignments
    """
    c = ctx.obj["config"]

    if encode:
        key = bytes((ctx.obj["directory"] / "config.yaml").open().read(), "utf-8")
    else:
        key = None

    history = read_assignments(ctx.obj["directory"], history=True, key=key)
    assignments = list(assignment(c, history))
    if save:
        store_assignments(ctx.obj["directory"], assignments, key=key)
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
    key = bytes((ctx.obj["directory"] / "config.yaml").open().read(), "utf-8")

    participant_emails = emails(c)
    assignments = read_assignments(ctx.obj["directory"], history=False, key=key)

    for gifter, giftee in assignments:
        gifter, giftee = gifter.capitalize(), giftee.capitalize()

        header = open(f"{ctx.obj['directory']}/email_header.txt").read()
        if real:
            content = (
                open(f"{ctx.obj['directory']}/content.txt")
                .read()
                .format(gifter=gifter, giftee=giftee, gifter_upper=gifter.upper())
            )
        else:
            content = (
                open(f"{ctx.obj['directory']}/content.txt")
                .read()
                .format(gifter="gifter", giftee="giftee", gifter_upper="gifter".upper())
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
        if real:
            part2 = MIMEText(html, "html")
        else:
            part2 = MIMEText(
                f"gifters {sorted(g[0] for g in assignments)} "
                f"have giftees {sorted(g[1] for g in assignments)}\n\n" + html,
                "html",
            )

        # Add HTML/plain-text parts to MIMEMultipart message
        # The email client will try to render the last part first
        # message.attach(part1)
        message.attach(part2)

        if real:
            send_email(
                c.sender, participant_emails[gifter.lower()], c.password, message
            )
        else:
            send_email(c.sender, c.sender, c.password, message)
            break
