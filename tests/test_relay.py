from email.message import EmailMessage

import pytest

from ss.relay import detect_tag, extract_text, html_to_text, process_message, route, strip_quoted

ASSIGNMENTS = [("a", "c"), ("c", "f"), ("f", "a"), ("b", "d"), ("d", "g"), ("g", "h"), ("h", "ana maria"), ("ana maria", "b")]


def raw_message(frm, to, body, subject="hello", html=None, **headers):
    msg = EmailMessage()
    msg["From"] = frm
    msg["To"] = to
    msg["Delivered-To"] = to
    msg["Subject"] = subject
    for k, v in headers.items():
        msg[k.replace("_", "-")] = v
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg.as_bytes()


def test_detect_tag():
    msg = EmailMessage()
    msg["To"] = "Santa <santa+to-santa@example.com>"
    assert detect_tag(msg, "santa@example.com") == "to-santa"
    msg = EmailMessage()
    msg["Delivered-To"] = "santa+to-giftee@example.com"
    msg["To"] = "santa@example.com"
    assert detect_tag(msg, "Santa@Example.com") == "to-giftee"
    msg = EmailMessage()
    msg["To"] = "santa@example.com"
    assert detect_tag(msg, "santa@example.com") is None
    msg = EmailMessage()
    msg["To"] = "santa+other@example.com"
    assert detect_tag(msg, "santa@example.com") is None


def test_route():
    assert route("to-giftee", "a", ASSIGNMENTS) == "c"  # a is c's santa
    assert route("to-santa", "c", ASSIGNMENTS) == "a"  # c writes to their santa, who is a
    assert route("to-santa", "b", ASSIGNMENTS) == "ana maria"
    assert route("to-giftee", "nobody", ASSIGNMENTS) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hi!\n\nWhat size?\n\nOn Mon, Nov 9, 2026 at 9:00 AM Secret Santa <s@x.com> wrote:\n> old stuff", "Hi!\n\nWhat size?"),
        ("Hi!\n\nOn Mon, Nov 9, 2026 at 9:00 AM Secret Santa\n<santa@example.com> wrote:\n\n> old", "Hi!"),
        ("Thanks\n-- \nWill Patton\nSenior Elf", "Thanks"),
        ("Thanks\n\nSent from my iPhone", "Thanks"),
        ("Yes please\n\n-----Original Message-----\nFrom: x", "Yes please"),
        ("Sure\n\nFrom: Secret Santa <s@x.com>\nSent: Monday\nTo: me\nSubject: hi\n\nblah", "Sure"),
        ("Sure\n________________________________\nFrom: Secret Santa", "Sure"),
        ("Only fresh text here.", "Only fresh text here."),
        ("> entirely quoted", ""),
    ],
)
def test_strip_quoted(text, expected):
    assert strip_quoted(text) == expected


def test_html_to_text_marks_gmail_quotes():
    html = (
        "<div dir='ltr'>Fresh words<div><br></div><div>second line</div></div>"
        "<div class='gmail_quote'><div>On Mon wrote:</div><blockquote>old words</blockquote></div>"
    )
    text = html_to_text(html)
    assert text.startswith("Fresh words")
    assert "> old words" in text
    assert strip_quoted(text) == "Fresh words\n\nsecond line"


def test_process_message_relays_anonymously(config, tmp_path):
    sent = []
    raw = raw_message("A Person <A@example.com>", "santa+to-giftee@example.com", "Hi!\n\nWhat size?\n\nOn Mon wrote:\n> quoted", subject="A letter for C")
    summary = process_message(config, tmp_path, raw, ASSIGNMENTS, 2026, lambda to, msg: sent.append((to, msg)))
    assert summary["status"] == "relayed" and summary["tag"] == "to-giftee"
    assert "recipient" not in summary
    (to, msg), = sent
    assert to == "c@example.com"
    html = msg.get_body(("html",)).get_content()
    assert "What size?" in html and "quoted" not in html
    assert "A Person" not in html and "A@example.com" not in html and "A letter for C" not in msg["Subject"]
    assert msg["Reply-To"].endswith("<santa+to-santa@example.com>")


def test_process_message_from_giftee_is_signed(config, tmp_path):
    sent = []
    raw = raw_message("e@example.com", "santa+to-santa@example.com", "Medium socks please")
    summary = process_message(config, tmp_path, raw, ASSIGNMENTS, 2026, lambda to, msg: sent.append((to, msg)))
    assert summary["status"] == "relayed"
    (to, msg), = sent
    assert to == "h@example.com"  # h is ana maria's santa
    assert "Ana Maria" in msg.get_body(("html",)).get_content()


@pytest.mark.parametrize(
    "frm, to, body, extra, reason",
    [
        ("stranger@example.com", "santa+to-santa@example.com", "hi", {}, "not a participant"),
        ("a@example.com", "santa@example.com", "hi", {}, "not addressed"),
        ("a@example.com", "santa+to-giftee@example.com", "> only quoted", {}, "empty"),
        ("santa@example.com", "santa+to-giftee@example.com", "hi", {}, "automatic or sent by santa"),
        ("a@example.com", "santa+to-giftee@example.com", "hi", {"Auto_Submitted": "auto-replied"}, "automatic"),
    ],
)
def test_process_message_skips(config, tmp_path, frm, to, body, extra, reason):
    sent = []
    summary = process_message(config, tmp_path, raw_message(frm, to, body, **extra), ASSIGNMENTS, 2026, lambda *a: sent.append(a))
    assert summary["status"] == "skipped" and reason in summary["reason"]
    assert not sent


def test_extract_text_prefers_plain(config):
    msg = EmailMessage()
    msg.set_content("plain words")
    msg.add_alternative("<p>html words</p>", subtype="html")
    assert extract_text(msg) == "plain words\n"
