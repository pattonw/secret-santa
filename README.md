# secret-santa 🤫🎅

Assigns secret santa pairs for a group, emails everyone a sealed letter that
opens on a small web page, and carries anonymous letters between gifters and
giftees through the santa inbox.

## What it does

1. **Assignments.** Everyone gives one gift and receives one gift. People in
   the same group (a couple, a household) are never paired, nobody gets a
   reciprocal pair, and pairings from previous years are strictly avoided
   when possible. Solved as a small integer program with scipy's HiGHS.
2. **Secrecy, even from the organizer.** Giftees are encrypted at rest with
   a key in `secret.key`, so the organizer can run everything and still take
   part fairly.
3. **Letters.** Each participant gets an email styled as a sealed letter with
   one button, "Open your letter", which links to a static reveal page. The
   assignment travels in the URL fragment, base64-encoded, so no server ever
   sees it and nobody reads it over your shoulder.
4. **Santa's Post.** The reveal page has two buttons: write to your Secret
   Santa, and write to your giftee. Both are `mailto:` links to plus-addressed
   versions of the santa inbox. A relay forwards each letter to the right
   person as a letter from Santa, with quoted text and signatures removed and
   `Reply-To` set so a plain reply goes straight back.

## Setup

```sh
git clone https://github.com/pattonw/secret-santa
cd secret-santa && uv tool install .     # or: pip install .
```

Create a config directory per group:

```
my-group/
  config.yaml
  secret.key        # created by `secret-santa my-group rekey`
  history/          # one encrypted <year>.json per year
  templates/        # optional overrides of the built-in email templates
```

`config.yaml`:

```yaml
family: The Pattons                      # shown on letters and the page
sender: our.secret.santa@gmail.com       # a Gmail account the organizer controls
password: an-app-password                # Gmail app password (IMAP and SMTP)
subject: "A letter from the North Pole for {{ gifter }}"
santa_name: Secret Santa                 # display name on outgoing mail
page_url: https://pattonw.github.io/secret-santa/
wishlist: https://docs.google.com/spreadsheets/d/...
deadline: November 25th
notes: Questions go in the family group chat.
allow_reciprocal: false                  # true only for two-person test runs

groups:
  couple ab:
    - { name: a, email: a@example.com }
    - { name: b, email: b@example.com }
  household cde:
    - { name: c, email: c@example.com }
    - { name: d, email: d@example.com }
    - { name: ana maria, email: e@example.com }
  uncle g:
    - { name: g, email: g@example.com }
```

Then generate a key before anything else:

```sh
secret-santa my-group rekey
```

## Each year

```sh
secret-santa my-group check                   # config and history sanity check
secret-santa my-group new-assignments --test  # prints a sample, saves nothing
secret-santa my-group new-assignments --save  # writes history/<year>.json, encrypted
secret-santa my-group render --open           # HTML previews of every email and the page
secret-santa my-group email --test            # one sample email to the santa address
secret-santa my-group email --real            # everyone gets their letter
```

Then keep the post running while people shop:

```sh
secret-santa my-group relay --dry-run         # show what would be relayed
secret-santa my-group relay                   # relay once (for cron / GitHub Actions)
secret-santa my-group relay --poll --interval 60
```

Other commands: `print-history`, `print-assignments` (both take `--decode`,
which reveals pairings to whoever runs it), `encode`, `recode-assignments`.

## The reveal page

`docs/index.html` is the static page served from GitHub Pages. It has no
data of its own; everything comes from the URL fragment, which is
base64url-encoded JSON:

| key | meaning |
|-----|---------|
| `g` | gifter display name |
| `t` | giftee display name |
| `y` | year |
| `s` | santa email address (for the mailto buttons) |
| `f`, `w`, `d`, `n` | family, wishlist URL, deadline, notes (optional) |

`render` copies the page next to the previews so links work offline.

## How the relay decides where a letter goes

| written to | who writes | who receives | the letter is signed |
|------------|------------|--------------|----------------------|
| `santa+to-santa@…` | a giftee | their secret santa | with the giftee's name |
| `santa+to-giftee@…` | a santa | their giftee | "Your Secret Santa" |

Messages from unknown senders, without a tag, or that are empty after
stripping quoted text are left in the inbox under the label
`Santa Relay/Skipped`. Attachments are not forwarded. Logs never print the
recipient of a letter.

## Templates

The built-in templates live in `ss/templates/` and are rendered with Jinja2.
Drop a file with the same name into `<config-dir>/templates/` to override one:
`assignment_email.html`, `assignment_email.txt`, `letter_email.html`,
`letter_email.txt`.

## Development

```sh
uv run --extra dev pytest
```
