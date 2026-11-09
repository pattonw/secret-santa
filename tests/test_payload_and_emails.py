from ss.emails import build_assignment_email, build_letter_email, plus_address
from ss.payload import assignment_link, assignment_payload, decode_payload, encode_payload


def test_payload_round_trip(config):
    payload = assignment_payload(config, "ana maria", "b", 2026)
    assert payload["g"] == "Ana Maria" and payload["t"] == "B" and payload["y"] == 2026
    token = encode_payload(payload)
    assert "=" not in token and "+" not in token and "/" not in token
    assert decode_payload(token) == payload


def test_link_shapes(config):
    assert assignment_link(config, "a", "b", 2026).startswith("https://example.github.io/secret-santa/#")
    assert assignment_link(config, "a", "b", 2026, base="/tmp/page.html").startswith("/tmp/page.html#")
    config.page_url = None
    assert assignment_link(config, "a", "b", 2026) is None


def test_assignment_email(config, tmp_path):
    msg = build_assignment_email(config, tmp_path, "ana maria", "b", 2026, "e@example.com")
    assert msg["Subject"] == "A letter for Ana Maria"
    assert msg["To"] == "e@example.com"
    html = msg.get_body(("html",)).get_content()
    text = msg.get_body(("plain",)).get_content()
    link = assignment_link(config, "ana maria", "b", 2026)
    assert link in html and link in text
    assert "B" not in html.split("Dear Ana Maria")[1].split("Open your letter")[0].replace("Break", "")  # giftee is not spelled out when there is a link


def test_assignment_email_without_page_names_the_giftee(config, tmp_path):
    config.page_url = None
    msg = build_assignment_email(config, tmp_path, "a", "ana maria", 2026, "a@example.com")
    assert "Ana Maria" in msg.get_body(("html",)).get_content()


def test_letter_from_santa_is_anonymous(config, tmp_path):
    msg = build_letter_email(
        config, tmp_path, tag="to-giftee", recipient="b", counterpart="a", body="Hi there\n\nWhat size?", year=2026, to="b@example.com"
    )
    html = msg.get_body(("html",)).get_content()
    assert msg["Reply-To"].endswith("<santa+to-santa@example.com>")
    assert "your Secret Santa" in html and ">A<" not in html
    assert "What size?" in html


def test_letter_from_giftee_is_signed(config, tmp_path):
    msg = build_letter_email(
        config, tmp_path, tag="to-santa", recipient="a", counterpart="ana maria", body="Thanks!", year=2026, to="a@example.com"
    )
    assert msg["Reply-To"].endswith("<santa+to-giftee@example.com>")
    assert "Ana Maria" in msg.get_body(("html",)).get_content()
    assert plus_address("x.y@gmail.com", "to-santa") == "x.y+to-santa@gmail.com"
