# secret-santa 🤫🎅

## Capabilities

1. Assign secret santa gifter/giftee pairs. Everyone will be a gifter and a giftee but all pairings will be kept secret.
2. Group constraints. People can be grouped arbitrarily. For example significant others can be grouped so that they won't be assigned to give each other gifts.
3. Avoid annual repeats. Historical assignments are tracked and repeat assignments are penalized.
4. Avoids pair-wise reciprocation. If person A is assigned to person B, person B won't be assigned to person A.
5. Automatically sends out emails to participants. The organizer does not need to know all the assignments and can participate fairly.
   - requires some additional setup. An email account to send the emails. Configured password, etc.

## Usage

1. git clone and pip install secret-santa package.
2. Create a config directory. Name is arbitrary:
   `mkdir path/to/ultimate-secret-santa`
3. Create a `config.yaml` file in your config directory.

`config.yaml` (sender, password, subject, and users emails are optional):

```yaml
sender: secret.santa.email@gmail.com
password: super_duper_secret_password
subject: {gifter}, You have a mission

groups:
  couple ab:
    -
      name: a
      email: a@gmail.com
    -
      name: b
      email: b@gmail.com
  fam cdef:
    -
      name: c
      email: c@gmail.com
    -
      name: d
      email: d@gmail.com
    -
      name: e
      email: d@gmail.com
    -
      name: f
      email: d@gmail.com
  uncle g:
    -
      name: g
      email: g@gmail.com
  aunts hij:
    -
      name: h
      email: h@gmail.com
    -
      name: i
      email: i@gmail.com
    -
      name: j
      email: j@gmail.com
```
This config would ensure a and b are not assigned to each other. c, d, e, f cannot be assigned to each other. h, i, j cannot be assigned to each other.