from __future__ import annotations

import shutil
import webbrowser
from pathlib import Path
from pprint import pprint

import click
from omegaconf import OmegaConf

from . import relay as relay_module
from .assignment import assignment, display_name, emails, participants
from .emails import (
    TAG_TO_GIFTEE,
    TAG_TO_SANTA,
    build_assignment_email,
    build_letter_email,
    plus_address,
    send_email,
)
from .payload import assignment_payload, page_link
from .store import (
    KEY_FILE,
    current_year,
    generate_key,
    has_key_file,
    history_files,
    load,
    load_key,
    read_assignments,
    rekey,
    store_assignments,
    write_assignments,
)

SAMPLE_LETTER_FROM_SANTA = (
    "I hear you like books, but your wishlist is looking a little bare. "
    "Is there anything you've been eyeing lately?\n\n"
    "Also, and this is important: what size socks do you wear?"
)
SAMPLE_LETTER_FROM_GIFTEE = (
    "Thanks for asking! I just added a few things to the wishlist. "
    "Honestly anything cozy would be great, it's been freezing here.\n\n"
    "Medium socks, if that's what the hint was about."
)


@click.group()
@click.argument("config-dir", type=click.Path(exists=True, file_okay=False))
@click.pass_context
def cli(ctx, config_dir):
    """
    CONFIG-DIR is the directory containing config.yaml, secret.key and the
    history/ folder for one secret santa group.
    """
    config_dir = Path(config_dir)
    ctx.ensure_object(dict)
    ctx.obj["config"] = OmegaConf.load(config_dir / "config.yaml")
    ctx.obj["directory"] = config_dir
    ctx.obj["key"] = load_key(config_dir)
    if not has_key_file(config_dir):
        click.secho(
            f"note: no {KEY_FILE} in {config_dir}; using config.yaml as the key. "
            "Run `rekey` before editing config.yaml.",
            err=True,
            fg="yellow",
        )


@cli.command()
@click.option("--decode/--raw", default=False, help="Decrypt the giftees so they are readable.")
@click.pass_context
def print_history(ctx, decode):
    """Print the history of annual assignments."""
    key = ctx.obj["key"] if decode else None
    history = read_assignments(ctx.obj["directory"], history=True, key=key)
    pprint({year: dict(pairs) for year, pairs in history.items()})


@cli.command()
@click.option("--decode/--raw", default=False, help="Decrypt the giftees so they are readable.")
@click.pass_context
def print_assignments(ctx, decode):
    """Print this year's assignments."""
    key = ctx.obj["key"] if decode else None
    pprint(dict(read_assignments(ctx.obj["directory"], history=False, key=key)))


@cli.command()
@click.argument("year", type=int)
@click.pass_context
def encode(ctx, year):
    """Encrypt a plaintext history/YEAR.json in place."""
    path = ctx.obj["directory"] / "history" / f"{year}.json"
    write_assignments(path, load(path), ctx.obj["key"])
    click.echo(f"encoded {path}")


@cli.command()
@click.option("--encode/--decode", default=False, help="Encode plaintext input, or decode encrypted input.")
@click.option("-in", "--input-file", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("-out", "--output-file", required=True, type=click.Path())
@click.pass_context
def recode_assignments(ctx, encode, input_file, output_file):
    """Copy an assignments file while encrypting or decrypting it."""
    key = ctx.obj["key"]
    if encode:
        write_assignments(Path(output_file), load(Path(input_file)), key=key)
    else:
        write_assignments(Path(output_file), load(Path(input_file), key=key), key=None)
    click.echo(f"wrote {output_file}")


@cli.command()
@click.pass_context
def rekey_cmd(ctx):
    """Create (or rotate) secret.key and re-encrypt all history with it.

    Older config directories used the text of config.yaml as the key, which
    meant any edit to the config made the history unreadable.  Run this once
    before editing config.yaml; afterwards edits are safe.
    """
    directory = ctx.obj["directory"]
    old_key = ctx.obj["key"]
    new_key = generate_key()
    files = rekey(directory, old_key, new_key)
    (directory / KEY_FILE).write_bytes(new_key + b"\n")
    click.echo(f"wrote {directory / KEY_FILE} and re-encoded {len(files)} history file(s)")


cli.add_command(rekey_cmd, name="rekey")


@cli.command()
@click.option(
    "--save/--test",
    default=False,
    help="Save to history/<year>.json, or just print to the terminal.",
)
@click.option("--encode/--raw", default=True, help="Encrypt the saved giftees. Even from you.")
@click.pass_context
def new_assignments(ctx, save, encode):
    """Create new assignments for this year."""
    c = ctx.obj["config"]
    key = ctx.obj["key"] if encode else None
    history = read_assignments(ctx.obj["directory"], history=True, key=key)
    pairs, repeats = assignment(c, history)
    click.echo(f"found an assignment for {len(pairs)} people with {repeats} historical repeat(s)")
    if save:
        path = store_assignments(ctx.obj["directory"], pairs, key=key)
        click.echo(f"saved to {path}")
    else:
        pprint(dict(pairs))


def _assignment_rows(ctx, real: bool):
    """(gifter, giftee, to-address) rows for emails and previews."""
    c = ctx.obj["config"]
    addresses = emails(c)
    if real:
        pairs = read_assignments(ctx.obj["directory"], history=False, key=ctx.obj["key"])
        for gifter, giftee in pairs:
            if not addresses.get(gifter):
                raise click.ClickException(f"{gifter} has no email address in config.yaml")
            yield gifter, giftee, addresses[gifter]
    else:
        yield "gifter", "giftee", str(c.sender)


@cli.command()
@click.option(
    "--real/--test",
    default=False,
    help="Send everyone their assignment, or send one sample (with placeholder names) to the santa address.",
)
@click.pass_context
def email(ctx, real):
    """Send out the assignment letters."""
    c = ctx.obj["config"]
    year = current_year()
    sent = 0
    for gifter, giftee, to in _assignment_rows(ctx, real):
        message = build_assignment_email(c, ctx.obj["directory"], gifter, giftee, year, to)
        send_email(str(c.sender), to, str(c.password), message)
        click.echo(f"sent {display_name(gifter)}'s letter to {to}")
        sent += 1
    click.echo(f"{sent} email(s) sent")


def _local_page() -> Path | None:
    candidate = Path(__file__).resolve().parents[1] / "docs" / "index.html"
    return candidate if candidate.exists() else None


@cli.command()
@click.option("--real/--test", default=False, help="Render every participant's real letter, or one sample.")
@click.option("--out", type=click.Path(file_okay=False), default=None, help="Output directory (default: <config-dir>/preview).")
@click.option("--open", "open_browser", is_flag=True, help="Open the preview index in a browser.")
@click.pass_context
def render(ctx, real, out, open_browser):
    """Write HTML previews of every email and the reveal page, without sending anything."""
    c = ctx.obj["config"]
    directory = ctx.obj["directory"]
    year = current_year()
    out = Path(out) if out else directory / "preview"
    out.mkdir(parents=True, exist_ok=True)

    local_page = _local_page()
    if local_page:
        shutil.copy(local_page, out / "page.html")
    page_base = str(out / "page.html") if local_page else c.get("page_url")
    if page_base and not str(page_base).startswith(("http://", "https://")):
        page_base = Path(page_base).resolve().as_uri()

    rows = list(_assignment_rows(ctx, real))
    sample_gifter, sample_giftee, _ = rows[0]
    links = []
    for gifter, giftee, to in rows:
        message = build_assignment_email(c, directory, gifter, giftee, year, to, page_base=page_base)
        name = f"assignment_email_{gifter.replace(' ', '_')}.html" if real else "assignment_email.html"
        (out / name).write_text(message.get_body(("html",)).get_content())
        links.append((f"Assignment email for {display_name(gifter)} (subject: {message['Subject']})", name))
        links.append(("  ↳ the reveal page it links to", page_link(page_base, assignment_payload(c, gifter, giftee, year)) if page_base else ""))

    for tag, body, name, label in (
        (TAG_TO_GIFTEE, SAMPLE_LETTER_FROM_SANTA, "letter_from_santa.html", "Letter from your Secret Santa"),
        (TAG_TO_SANTA, SAMPLE_LETTER_FROM_GIFTEE, "letter_from_giftee.html", "Letter from your giftee"),
    ):
        recipient, counterpart = (sample_giftee, sample_gifter) if tag == TAG_TO_GIFTEE else (sample_gifter, sample_giftee)
        letter = build_letter_email(
            c, directory, tag=tag, recipient=recipient, counterpart=counterpart, body=body, year=year, to="preview@example.com", page_base=page_base,
        )
        (out / name).write_text(letter.get_body(("html",)).get_content())
        links.append((f"{label} (subject: {letter['Subject']}, reply-to: {letter['Reply-To']})", name))

    items = "\n".join(
        f'<li><a href="{href}">{label}</a></li>' if href else f"<li>{label}</li>" for label, href in links
    )
    (out / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Secret santa previews</title>"
        "<body style='font:16px/1.6 system-ui;max-width:52rem;margin:3rem auto;padding:0 1rem'>"
        f"<h1>Previews for {c.get('family', directory.name)} {year}</h1><ol>{items}</ol>"
        "<p>Nothing here was sent. Delete this folder whenever you like.</p>"
    )
    click.echo(f"wrote {len(links)} preview(s) to {out}")
    click.echo((out / "index.html").as_uri())
    if open_browser:
        webbrowser.open((out / "index.html").as_uri())


@cli.command()
@click.option("--once/--poll", default=True, help="Check the inbox once, or keep polling.")
@click.option("--interval", default=60, show_default=True, help="Seconds between polls.")
@click.option("--dry-run", is_flag=True, help="Report what would be relayed without sending or marking anything.")
@click.pass_context
def relay(ctx, once, interval, dry_run):
    """Forward letters between gifters and giftees through the santa inbox.

    Participants write to <santa>+to-santa@... or <santa>+to-giftee@...
    (the reveal page has buttons for both).  Letters are re-sent from the
    santa address with quoted text and signatures removed, and Reply-To set
    so a normal reply goes back the other way.
    """
    c = ctx.obj["config"]
    directory = ctx.obj["directory"]
    year = current_year()

    def current():
        return read_assignments(directory, history=False, key=ctx.obj["key"])

    current()  # fail early if this year's assignments don't exist yet
    if once:
        summaries = relay_module.relay_once(c, directory, current(), year, dry_run=dry_run, log=click.echo)
        relayed = sum(s["status"] == "relayed" for s in summaries)
        click.echo(f"{relayed} letter(s) relayed, {len(summaries) - relayed} skipped")
    else:
        click.echo(f"polling {c.sender} every {interval}s, ctrl-c to stop")
        relay_module.relay_forever(c, directory, current, year, interval, dry_run=dry_run, log=click.echo)


@cli.command()
@click.pass_context
def check(ctx):
    """Validate the config: participants, emails, groups, and that history decrypts."""
    c = ctx.obj["config"]
    people = participants(c)
    groups = {}
    for p in people.values():
        groups.setdefault(p.group, []).append(p.display)
    click.echo(f"{len(people)} participants in {len(groups)} groups:")
    for group, members in groups.items():
        click.echo(f"  {group}: {', '.join(members)}")
    missing = [p.display for p in people.values() if not p.email]
    if missing:
        click.secho(f"missing email for: {', '.join(missing)}", fg="yellow")
    for field in ("sender", "password", "subject"):
        if not c.get(field):
            click.secho(f"config.yaml is missing `{field}`", fg="red")
    for field in ("family", "page_url", "wishlist", "deadline"):
        if not c.get(field):
            click.secho(f"config.yaml has no `{field}` (optional, used by the emails and page)", fg="yellow")
    files = history_files(ctx.obj["directory"])
    try:
        read_assignments(ctx.obj["directory"], history=True, key=ctx.obj["key"])
        click.echo(f"{len(files)} history file(s) decrypt with the current key")
    except Exception as exc:
        click.secho(f"history does not decrypt with the current key: {exc!r}", fg="red")
        if not has_key_file(ctx.obj["directory"]):
            click.echo("config.yaml was probably edited; restore it, run `rekey`, then redo the edit")
    click.echo(f"santa post addresses: {plus_address(c.sender, TAG_TO_SANTA) if c.get('sender') else '?'}, "
               f"{plus_address(c.sender, TAG_TO_GIFTEE) if c.get('sender') else '?'}")
