from django import forms

from apps.moderation.models import MAX_PUBLIC_NOTE_LENGTH
from apps.moderation.rules import VERDICT_ACTS, Act

MAX_NOTES_LENGTH = 2000


class ConfirmActionForm(forms.Form):
    """The notes a moderator may add on the confirmation page. Lengths count code points, as the
    database column and the author's view do."""

    public_note = forms.CharField(
        max_length=MAX_PUBLIC_NOTE_LENGTH,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "cols": 80}),
    )
    notes = forms.CharField(
        label="Internal notes",
        help_text="Only moderators see these. They are kept in the moderation log.",
        max_length=MAX_NOTES_LENGTH,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "cols": 80}),
    )

    def __init__(self, *args, act, **kwargs):
        super().__init__(*args, **kwargs)
        if act in VERDICT_ACTS:
            self.fields["public_note"].label = "Public note"
            self.fields[
                "public_note"
            ].help_text = "Shown with the label on the post. Leave blank for none."
        elif act == Act.REMOVE:
            self.fields["public_note"].label = "Reason shown to the author"
            self.fields[
                "public_note"
            ].help_text = "The author sees this with the removal. Leave blank to give no reason."
        else:
            del self.fields["public_note"]
