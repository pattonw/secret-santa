"""Anonymous post between gifters and giftees.

Participants write to ``<santa>+to-santa@...`` or ``<santa>+to-giftee@...``.
The relay reads the santa inbox over IMAP, works out who wrote and in which
direction, strips quoted text and signatures, and re-sends the message as a
letter from the santa account with ``Reply-To`` set so a plain reply goes
straight back the other way.
"""

from __future__ import annotations

import email
import imaplib
import re
import time
from email import policy
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from html.parser import HTMLParser

from .assignment import by_email, display_name, emails, normalize
from .emails import TAG_TO_GIFTEE, TAG_TO_SANTA, TAGS, build_letter_email, send_email

IMAP_HOST = "imap.gmail.com"
RELAY_LABEL = "Santa Relay"
SKIPPED_LABEL = "Santa Relay/Skipped"

ADDRESS_HEADERS = ("Delivered-To", "To", "Cc", "X-Original-To", "Envelope-To", "X-Forwarded-To")


def detect_tag(message, sender: str) -> str | None:
    """Which plus-tag was this message sent to, if any."""
    local, _, domain = str(sender).lower().partition("@")
    addresses = []
    for header in ADDRESS_HEADERS:
        for value in message.get_all(header, []):
            addresses += [addr for _, addr in getaddresses([str(value)])]
    for address in addresses:
        addr_local, _, addr_domain = address.lower().partition("@")
        if addr_domain == domain and addr_local.startswith(local + "+"):
            tag = addr_local[len(local) + 1:]
            if tag in TAGS:
                return tag
    return None


def route(tag: str, writer: str, assignments) -> str | None:
    """Who should receive a letter written by ``writer`` on ``tag``."""
    for gifter, giftee in assignments:
        if tag == TAG_TO_SANTA and normalize(giftee) == writer:
            return normalize(gifter)
        if tag == TAG_TO_GIFTEE and normalize(gifter) == writer:
            return normalize(giftee)
    return None


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "table", "section"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0
        self.quote = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
        if tag == "blockquote" or ("class", "gmail_quote") in attrs:
            self.quote += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.skip = max(0, self.skip - 1)
        if tag == "blockquote":
            self.quote = max(0, self.quote - 1)
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        if self.quote:
            data = "".join("> " + line for line in data.splitlines(keepends=True))
        self.parts.append(data)

    def text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.text()


def extract_text(message) -> str:
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    content = body.get_content()
    if body.get_content_type() == "text/html":
        content = html_to_text(content)
    return content


_CUT_PATTERNS = [
    re.compile(r"^On .{0,200}wrote:$", re.S),
    re.compile(r"^-{2,}\s*(Original Message|Forwarded message)\s*-{2,}", re.I),
    re.compile(r"^_{5,}$"),
    re.compile(r"^Sent from (my|Mail for) ", re.I),
    re.compile(r"^Get Outlook for ", re.I),
    re.compile(r"^(Le .{0,120} a écrit|Am .{0,120} schrieb .{0,40}|El .{0,120} escribió)\s*:$"),
]


def strip_quoted(text: str) -> str:
    """Keep only the freshly written part of an email body."""
    lines = text.replace("\r\n", "\n").split("\n")
    cut = len(lines)
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(">") or s in ("--", "—"):
            cut = i
            break
        if any(p.match(s) for p in _CUT_PATTERNS):
            cut = i
            break
        # "On <date> <name> wrote:" wrapped over two lines
        if s.startswith("On ") and i + 1 < len(lines) and lines[i + 1].strip().endswith("wrote:"):
            cut = i
            break
        # Outlook style header block
        if re.match(r"^\*?From:\*? .+", s) and any(
            re.match(r"^\*?(Sent|Date|To):\*? ", later.strip()) for later in lines[i + 1 : i + 4]
        ):
            cut = i
            break
    return "\n".join(lines[:cut]).strip()


def is_automatic(message) -> bool:
    auto = str(message.get("Auto-Submitted", "no")).lower()
    precedence = str(message.get("Precedence", "")).lower()
    return (auto and auto != "no") or precedence in ("bulk", "junk", "auto_reply", "list")


def process_message(config, config_dir, raw: bytes, assignments, year: int, send, page_base=None) -> dict:
    """Decide what to do with one raw message.  Returns a summary dict with a
    ``status`` of relayed / skipped and a ``reason``.  Never includes the
    recipient's name so logs don't leak pairings."""
    message = email.message_from_bytes(raw, policy=policy.default)
    sender = str(config.sender).lower()
    _, from_address = parseaddr(str(message.get("From", "")))
    from_address = from_address.lower()
    summary = {"from": from_address, "subject": str(message.get("Subject", "")), "status": "skipped"}

    if not from_address or from_address.split("+")[0] == sender.split("+")[0] or is_automatic(message):
        summary["reason"] = "automatic or sent by santa"
        return summary
    writer = by_email(config).get(from_address)
    if writer is None:
        summary["reason"] = "sender is not a participant"
        return summary
    tag = detect_tag(message, sender)
    if tag is None:
        summary["reason"] = "not addressed to +to-santa or +to-giftee"
        return summary
    body = strip_quoted(extract_text(message))
    if not body:
        summary["reason"] = "empty after removing quoted text"
        return summary
    recipient = route(tag, writer, assignments)
    if recipient is None:
        summary["reason"] = "no assignment found for sender"
        return summary
    recipient_email = emails(config).get(recipient)
    if not recipient_email:
        summary["reason"] = "recipient has no email"
        return summary

    letter = build_letter_email(
        config, config_dir, tag=tag, recipient=recipient, counterpart=writer, body=body, year=year, to=recipient_email, page_base=page_base,
    )
    send(recipient_email, letter)
    summary.update(status="relayed", tag=tag, writer=display_name(writer), chars=len(body))
    return summary


def relay_once(config, config_dir, assignments, year: int, dry_run: bool = False, log=print) -> list[dict]:
    """Process every unseen message in the santa inbox once."""
    sender, password = str(config.sender), str(config.password)

    def send(to, letter: EmailMessage):
        if dry_run:
            return
        send_email(sender, to, password, letter)

    summaries = []
    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(sender, password)
        imap.select("INBOX")
        status, data = imap.uid("search", None, "UNSEEN")
        uids = data[0].split() if status == "OK" and data and data[0] else []
        for uid in uids:
            status, parts = imap.uid("fetch", uid, "(BODY.PEEK[])")
            if status != "OK" or not parts or parts[0] is None:
                continue
            raw = parts[0][1]
            try:
                summary = process_message(config, config_dir, raw, assignments, year, send)
            except Exception as exc:  # leave the message unseen for a retry
                log(f"error handling message {uid.decode()}: {exc!r}")
                continue
            summaries.append(summary)
            label = RELAY_LABEL if summary["status"] == "relayed" else SKIPPED_LABEL
            if summary["status"] == "relayed":
                log(f"relayed a letter from {summary['writer']} ({summary['tag']}, {summary['chars']} chars)")
            else:
                log(f"skipped message from {summary['from']}: {summary['reason']}")
            if not dry_run:
                imap.uid("store", uid, "+FLAGS", "(\\Seen)")
                try:
                    imap.uid("store", uid, "+X-GM-LABELS", f'("{label}")')
                except imaplib.IMAP4.error:
                    pass
    return summaries


def relay_forever(config, config_dir, read_assignments, year: int, interval: int, dry_run=False, log=print):
    """Poll until interrupted.  ``read_assignments`` is a callable so a fresh
    history file is picked up without restarting."""
    while True:
        try:
            relay_once(config, config_dir, read_assignments(), year, dry_run=dry_run, log=log)
        except (imaplib.IMAP4.error, OSError) as exc:
            log(f"relay error, will retry: {exc!r}")
        time.sleep(interval)
