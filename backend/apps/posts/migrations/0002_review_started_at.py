from django.conf import settings
from django.db import migrations, models
from django.db.models import F


def start_the_clock_of_posts_under_review(apps, schema_editor):
    """Posts already under review (dev databases only) get `updated_at` as the start of their wait:
    the move into review was their last write. The queue's age is a little short for them, which
    is fine for development data; the check below needs every such post to have a value."""
    Post = apps.get_model("posts", "Post")
    Post.objects.filter(status="under_review").update(review_started_at=F("updated_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("posts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="post",
            name="posts_review_queue_idx",
        ),
        migrations.AddField(
            model_name="post",
            name="review_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(start_the_clock_of_posts_under_review, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(
                condition=models.Q(("status", "under_review")),
                fields=["review_started_at"],
                name="posts_review_queue_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="post",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("review_started_at__isnull", False), ("status", "under_review")),
                    models.Q(
                        models.Q(("status", "under_review"), _negated=True),
                        ("review_started_at__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="posts_post_review_started_consistent",
            ),
        ),
    ]
