"""Build and send the two kinds of email: the assignment letter and relayed
letters between a gifter and their giftee."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader, select_autoescape

from .assignment import display_name
from .payload import assignment_link

TAG_TO_SANTA = "to-santa"  # a giftee writing to their (unknown) secret santa
TAG_TO_GIFTEE = "to-giftee"  # a santa writing to their (known) giftee
TAGS = (TAG_TO_SANTA, TAG_TO_GIFTEE)


def plus_address(sender: str, tag: str) -> str:
    local, _, domain = str(sender).partition("@")
    return f"{local}+{tag}@{domain}"


def template_env(config_dir) -> Environment:
    loaders = []
    overrides = Path(config_dir) / "templates"
    if overrides.is_dir():
        loaders.append(FileSystemLoader(str(overrides)))
    loaders.append(PackageLoader("ss", "templates"))
    return Environment(
        loader=ChoiceLoader(loaders),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(config_dir, template_name: str, **context) -> str:
    return template_env(config_dir).get_template(template_name).render(**context)


def render_string(text: str, **context) -> str:
    return Environment(autoescape=False).from_string(str(text)).render(**context)


def santa_from(config) -> str:
    return formataddr((str(config.get("santa_name", "Secret Santa")), str(config.sender)))


def base_context(config, year: int) -> dict:
    return {
        "year": year,
        "family": config.get("family"),
        "deadline": config.get("deadline"),
        "wishlist": config.get("wishlist"),
        "notes": config.get("notes"),
        "sender": str(config.sender),
        "santa_name": config.get("santa_name", "Secret Santa"),
        "to_santa_address": plus_address(config.sender, TAG_TO_SANTA),
        "to_giftee_address": plus_address(config.sender, TAG_TO_GIFTEE),
    }


def assignment_context(config, gifter: str, giftee: str, year: int, page_base: str | None = None) -> dict:
    context = base_context(config, year)
    context.update(
        gifter=display_name(gifter),
        giftee=display_name(giftee),
        link=assignment_link(config, gifter, giftee, year, base=page_base),
    )
    return context


def build_assignment_email(config, config_dir, gifter: str, giftee: str, year: int, to: str, page_base=None) -> EmailMessage:
    context = assignment_context(config, gifter, giftee, year, page_base=page_base)
    message = EmailMessage()
    message["Subject"] = render_string(config.subject, **context)
    message["From"] = santa_from(config)
    message["To"] = to
    message.set_content(render(config_dir, "assignment_email.txt", **context))
    message.add_alternative(render(config_dir, "assignment_email.html", **context), subtype="html")
    return message


def letter_context(config, *, tag: str, recipient: str, counterpart: str, body: str, year: int, page_base=None) -> dict:
    """``tag`` is the plus-tag the letter arrived on.  ``recipient`` is who
    gets this email and ``counterpart`` is the other half of the pairing."""
    context = base_context(config, year)
    paragraphs = [p.strip() for p in body.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if tag == TAG_TO_GIFTEE:
        # recipient is the giftee; the writer is their anonymous santa
        context.update(
            anonymous=True,
            from_label="your Secret Santa",
            signature="Your Secret Santa",
            reply_label="your Secret Santa",
            reply_address=plus_address(config.sender, TAG_TO_SANTA),
            reply_subject="A letter for my Secret Santa",
            subject="A letter from your Secret Santa",
            link=assignment_link(config, recipient, counterpart, year, base=page_base),
        )
    else:
        # recipient is the santa; the writer is their giftee, whom they know
        name = display_name(counterpart)
        context.update(
            anonymous=False,
            from_label=f"{name}, your giftee",
            signature=name,
            reply_label=name,
            reply_address=plus_address(config.sender, TAG_TO_GIFTEE),
            reply_subject=f"A letter for {name}",
            subject=f"A letter from {name}",
            link=assignment_link(config, recipient, counterpart, year, base=page_base),
        )
    context.update(recipient=display_name(recipient), paragraphs=paragraphs, body=body)
    return context


def build_letter_email(config, config_dir, *, tag: str, recipient: str, counterpart: str, body: str, year: int, to: str, page_base=None) -> EmailMessage:
    context = letter_context(config, tag=tag, recipient=recipient, counterpart=counterpart, body=body, year=year, page_base=page_base)
    message = EmailMessage()
    message["Subject"] = "\U0001f48c " + context["subject"]
    message["From"] = santa_from(config)
    message["To"] = to
    message["Reply-To"] = formataddr((f"Reply to {context['reply_label']}", context["reply_address"]))
    message.set_content(render(config_dir, "letter_email.txt", **context))
    message.add_alternative(render(config_dir, "letter_email.html", **context), subtype="html")
    return message


def send_email(sender_email: str, receiver_email: str, password: str, message: EmailMessage):
    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=context)
        server.login(sender_email, password)
        server.send_message(message, from_addr=sender_email, to_addrs=[receiver_email])
