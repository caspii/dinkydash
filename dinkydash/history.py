"""The rolling record of what was written recently.

Fed back into the prompt so the dashboard doesn't tell you the same octopus fact
every fortnight.

Pure: this decides what the history says, `dinkydash.store` decides where it
is kept. On a Pi that is a JSON file; hosted it is a table.
"""


def recent_notes(history, days):
    """Just the note text from the last `days` entries."""
    return [entry.get("note", "") for entry in history[-days:] if entry.get("note")]


def appended(history, entry, keep=30):
    """The history with one more entry on the end, trimmed to the last `keep`."""
    return (list(history) + [entry])[-keep:]
