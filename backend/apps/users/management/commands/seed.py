from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.comments.models import Comment
from apps.communities.models import Community, CommunityRule, Flair, Membership
from apps.messaging.models import Conversation, Message
from apps.moderation.models import Report
from apps.notifications.models import Notification
from apps.polls.models import Poll, PollOption, PollVote
from apps.posts.models import Post
from apps.saves.models import SavedItem
from apps.social.models import Follow
from apps.votes.models import Vote

User = get_user_model()

DEFAULT_PASSWORD = "password123"

USERS = [
    ("ada", "Backend engineer. I like databases and strong consistency."),
    ("linus", "Kernel hacker. Opinions are my own and usually loud."),
    ("grace", "Compiler nerd, debugging enthusiast, mother of bugs."),
    ("margaret", "Wrote the code that went to the moon. Now I lurk."),
    ("dennis", "C is fine, actually. Fight me in the comments."),
    ("katherine", "Rocket math. I still check everything twice."),
    ("alan", "Can a machine think? Can this feed load faster?"),
    ("hedy", "Inventor by night. Frequency hopping is underrated."),
    ("tim", "Made a web thing once. Please use semantic HTML."),
    ("radia", "Spanning trees and calm networks. Keep it loop-free."),
    ("barbara", "Abstraction is the whole job. Everything else is typing."),
    ("donald", "Premature optimization warnings, volume 4."),
    ("guido", "Readability counts. Whitespace is not the enemy."),
    ("bjarne", "There are only two kinds of languages, you know the rest."),
    ("ken", "Small tools, composed well. Also: chess."),
    ("brendan", "Prototyped a language in ten days. It stuck."),
    ("anders", "Type systems that meet you halfway."),
    ("vint", "Packets find a way. Be liberal in what you accept."),
    ("sophie", "Game engines by day, shader art by night."),
    ("annie", "Bug bounty hunter. I read your error messages."),
    ("edsger", "GOTO considered harmful; naps considered essential."),
    ("niklaus", "Algorithms + Data Structures = Posts."),
    ("frances", "Compilers for people who hate compilers."),
    ("john", "Lisp in production. Yes, really."),
]

COMMUNITIES = [
    {
        "slug": "python",
        "name": "Python",
        "description": "Everything Python — from asyncio to zoneinfo.",
        "rules": ["Be kind", "No low-effort posts", "Search before asking"],
        "flairs": [("Help", "#3b82f6"), ("Showcase", "#22c55e"), ("News", "#eab308")],
    },
    {
        "slug": "webdev",
        "name": "Web Development",
        "description": "Frontend, backend, and the eternal war between them.",
        "rules": ["Stay on topic", "No hiring posts", "Credit your sources"],
        "flairs": [("Frontend", "#ec4899"), ("Backend", "#8b5cf6"), ("Career", "#14b8a6")],
    },
    {
        "slug": "askscience",
        "name": "Ask Science",
        "description": "Real questions, sourced answers, no hand-waving.",
        "rules": ["Cite sources", "No pseudoscience", "Explain like it matters"],
        "flairs": [("Physics", "#ef4444"), ("Biology", "#84cc16"), ("Meta", "#64748b")],
    },
    {
        "slug": "gamedev",
        "name": "Game Dev",
        "description": "Ship your game. Or at least a devlog about it.",
        "rules": ["Devlogs welcome", "No asset flips", "Tag NSFW content"],
        "flairs": [("Devlog", "#f97316"), ("Feedback", "#06b6d4"), ("Release", "#a855f7")],
    },
    {
        "slug": "rust",
        "name": "Rust",
        "description": "Fearless concurrency, fearful compile times.",
        "rules": ["Be patient with beginners", "No language wars", "Mark unsafe code"],
        "flairs": [("Help", "#f59e0b"), ("Crate", "#10b981"), ("RFC", "#6366f1")],
    },
    {
        "slug": "linux",
        "name": "Linux",
        "description": "Distros, dotfiles, and the year of the desktop.",
        "rules": ["No distro flamewars", "Include logs with bug posts", "Search first"],
        "flairs": [("Desktop", "#0ea5e9"), ("Server", "#78716c"), ("Kernel", "#dc2626")],
    },
    {
        "slug": "machinelearning",
        "name": "Machine Learning",
        "description": "Papers, models, and the occasional reality check.",
        "rules": ["Link the paper", "No AGI doomposting", "Share reproducible code"],
        "flairs": [("Paper", "#8b5cf6"), ("Discussion", "#14b8a6"), ("Project", "#f43f5e")],
    },
    {
        "slug": "askhistorians",
        "name": "Ask Historians",
        "description": "In-depth, sourced answers to historical questions.",
        "rules": ["Sources required", "No 20-year rule violations", "Be thorough"],
        "flairs": [("Ancient", "#b45309"), ("Modern", "#334155"), ("Meta", "#64748b")],
    },
    {
        "slug": "photocritique",
        "name": "Photo Critique",
        "description": "Post your shots, get honest feedback. Mods approve submissions.",
        "rules": ["Critique the photo, not the person", "Include EXIF if asked"],
        "flairs": [("Portrait", "#e879f9"), ("Landscape", "#22c55e"), ("Street", "#f59e0b")],
        "requires_approval": True,
    },
    {
        "slug": "afterdark",
        "name": "After Dark",
        "description": "18+ discussions. Everything here is age-gated.",
        "rules": ["18+ only", "Tag everything NSFW", "No harassment"],
        "flairs": [("Discussion", "#ef4444"), ("Story", "#a855f7")],
        "is_nsfw": True,
    },
]

# slug → list of (kind, title, body)
POST_SEEDS = {
    "python": [
        ("text", "Why does my asyncio task never run?", "I `await`-ed it but nothing happens."),
        (
            "text",
            "TIL dict preserves insertion order since 3.7",
            "It's a language guarantee now, not just a CPython detail.",
        ),
        ("link", "The best explanation of the GIL I've ever read", ""),
        (
            "text",
            "Type hints changed how I write code",
            "Not for the runtime — for the reviewer six months from now.",
        ),
        (
            "text",
            "Postgres full-text search is underrated",
            "You probably don't need Elasticsearch yet. Really.",
        ),
        (
            "text",
            "3.13 free-threading: who has tried it in anger?",
            "Benchmarks look promising but I want war stories, not microbenchmarks.",
        ),
        ("link", "uv is fast enough to change your workflow", ""),
        (
            "text",
            "Dataclasses vs Pydantic vs attrs in 2026",
            "Where do you draw the line between stdlib and dependencies?",
        ),
    ],
    "webdev": [
        (
            "text",
            "React 19 use() hook first impressions",
            "Suspense-friendly data reads feel great once it clicks.",
        ),
        ("link", "A tiny CSS reset that just works", ""),
        ("image", "Screenshot of my new dashboard", ""),
        (
            "text",
            "Stop shipping 2MB of JavaScript for a blog",
            "Server-render the words. Hydrate the widgets. That's it, that's the post.",
        ),
        (
            "text",
            "How do you handle auth tokens in SPAs?",
            "httpOnly cookies vs localStorage — convince me either way.",
        ),
        ("link", "Container queries finally killed my resize hooks", ""),
        (
            "text",
            "Tailwind v4 migration notes",
            "The CSS-first config took an afternoon. Worth it for the build speed.",
        ),
    ],
    "askscience": [
        (
            "text",
            "Why is the sky blue, really?",
            "I know it's Rayleigh scattering but explain the wavelength part.",
        ),
        (
            "text",
            "Do we actually know how anesthesia works?",
            "Asking because it terrifies and fascinates me.",
        ),
        (
            "text",
            "If mitochondria have their own DNA, where did it come from?",
            "Endosymbiosis sounds made up and I want details.",
        ),
        (
            "text",
            "Why can't we just make water from hydrogen and oxygen?",
            "We can, right? Why isn't this how we fix droughts?",
        ),
        (
            "text",
            "What does 'observing' collapse in quantum mechanics actually mean?",
            "Does a rock count as an observer? A camera? Please be gentle.",
        ),
        ("link", "A readable explainer on CRISPR off-target effects", ""),
    ],
    "gamedev": [
        (
            "text",
            "Devlog: shipped my roguelike demo",
            "Six months of nights and weekends. AMA about scope creep.",
        ),
        ("link", "Free low-poly asset pack for jams", ""),
        (
            "text",
            "ECS was overkill for my puzzle game",
            "Sometimes an array of structs is just fine. Lessons learned inside.",
        ),
        (
            "text",
            "How do you playtest with strangers without dying inside?",
            "Watching someone miss the tutorial button for 5 minutes is brutal.",
        ),
        ("image", "My water shader after 3 weeks of tweaking", ""),
        (
            "text",
            "Godot vs Unity in 2026 for a solo dev",
            "I know, I know. But the licensing story matters now.",
        ),
    ],
    "rust": [
        (
            "text",
            "The borrow checker finally clicked for me",
            "It took a linked list, three lifetimes, and one existential crisis.",
        ),
        ("link", "This crate cut our build times by 40%", ""),
        (
            "text",
            "async Rust: still worth the pain?",
            "Pin, Send bounds, and executor lock-in — is it me or is it hard?",
        ),
        (
            "text",
            "Rewrote our Python service in Rust — numbers inside",
            "p99 went from 240ms to 9ms. Memory from 1.2GB to 60MB.",
        ),
        (
            "text",
            "unsafe is not a code smell",
            "It's a contract. Wrap it, document it, test it, move on.",
        ),
    ],
    "linux": [
        (
            "text",
            "systemd timers replaced all my cron jobs",
            "OnCalendar= is genuinely nicer once you learn the syntax.",
        ),
        ("image", "My riced desktop, 40 hours of config for this screenshot", ""),
        (
            "text",
            "Wayland in 2026: what still breaks for you?",
            "Screen sharing works now. Color management is... getting there.",
        ),
        ("link", "A deep dive into how io_uring actually works", ""),
        (
            "text",
            "Btrfs snapshots saved me from myself again",
            "rm -rf'd the wrong directory. Rolled back in 30 seconds.",
        ),
    ],
    "machinelearning": [
        (
            "text",
            "Small models are eating the benchmark charts",
            "Distillation + better data beats parameter count for most tasks.",
        ),
        ("link", "Paper: attention sinks explain streaming LLM stability", ""),
        (
            "text",
            "How do you version datasets at your org?",
            "Git LFS groans, DVC confuses the team, S3 prefixes everywhere.",
        ),
        (
            "text",
            "RAG is a retrieval problem, not a prompting problem",
            "Fix your chunking and embeddings before touching the prompt.",
        ),
        (
            "text",
            "Reproduced a NeurIPS paper — results didn't replicate",
            "Off by 11 points. Author's code has a hardcoded seed. Now what?",
        ),
    ],
    "askhistorians": [
        (
            "text",
            "How did sailors actually navigate before GPS?",
            "Dead reckoning sounds terrifying. How lost did they get?",
        ),
        (
            "text",
            "Why did the Library of Alexandria decline, really?",
            "Was it one fire or centuries of budget cuts?",
        ),
        (
            "text",
            "What did ordinary Romans eat for breakfast?",
            "Not the banquets — the street food and the workers' meals.",
        ),
        (
            "text",
            "How new is the concept of a 'weekend'?",
            "When did two consecutive days off become normal?",
        ),
    ],
    "photocritique": [
        ("image", "Golden hour portrait, first attempt with a reflector", ""),
        ("image", "Foggy pier at dawn — too much negative space?", ""),
        ("image", "Street shot in the rain, shutter dragged to 1/15", ""),
        ("image", "High-contrast B&W alley — thoughts on the crop?", ""),
    ],
    "afterdark": [
        (
            "text",
            "How do you talk about dating apps without cringing?",
            "Serious discussion about profile honesty. 18+ takes only.",
        ),
        (
            "text",
            "Late-night confessions thread",
            "Anonymous-ish. Be kind, tag appropriately.",
        ),
        ("text", "Horror movies that earn the R rating", "Not gore for gore's sake — dread."),
    ],
}

# slug → (question, options)
POLL_SEEDS = {
    "python": ("Tabs or spaces, settle it forever", ["Tabs", "Spaces", "Both, unapologetically"]),
    "webdev": ("Best language for a first project?", ["Python", "JavaScript", "Go", "Rust"]),
    "linux": ("Your daily driver distro?", ["Arch-based", "Debian-based", "Fedora", "NixOS"]),
    "gamedev": ("Solo dev engine of choice?", ["Godot", "Unity", "Unreal", "Custom/other"]),
}

COMMENTS = [
    "Great question — I hit this exact wall last week.",
    "You forgot to actually schedule the coroutine. Wrap it in a task.",
    "Source? This contradicts what I learned in school.",
    "This is the way.",
    "Underrated take. Saving this thread.",
    "Works on my machine ¯\\_(ツ)_/¯",
    "Have you profiled it? I bet the bottleneck isn't where you think.",
    "Congrats on shipping! The scope discipline shows.",
    "Counterpoint: it depends entirely on your team's context.",
    "Thanks, this finally made it click for me.",
    "I wrote about this exact problem last year — happy to share notes.",
    "Bold claim. Do you have benchmarks?",
    "The docs actually cover this, but you have to read the footnotes.",
    "Came for the title, stayed for the comment section.",
    "Please post a follow-up when you figure it out.",
    "Half agree. The other half of me has been burned before.",
    "This should be pinned honestly.",
    "Tried this in production. It went... fine. Mostly fine.",
    "Reading this at 2am and now I have to refactor everything.",
    "Strong disagree, but upvoted for the discussion.",
]

REPLY_COMMENTS = [
    "Exactly this. Wish I could upvote twice.",
    "Hmm, that hasn't been my experience at all.",
    "Can you expand on that? Genuinely curious.",
    "This reply deserves its own post.",
    "OK this convinced me.",
    "We run this at scale and it holds up.",
    "That's fair, I was being a bit absolute.",
]

LINKS = [
    "https://example.com/gil-explained",
    "https://example.com/css-reset",
    "https://example.com/asset-pack",
    "https://example.com/blog/postgres-fts",
    "https://example.com/io-uring-deep-dive",
    "https://example.com/attention-sinks-paper",
    "https://example.com/container-queries",
    "https://example.com/fast-crate",
    "https://example.com/uv-workflow",
    "https://example.com/crispr-explainer",
]

DM_OPENERS = [
    "Hey, loved your post on the Python board!",
    "Are you going to the meetup next week?",
    "Quick question about your devlog — mind if I DM?",
    "That comment thread was gold, thanks for engaging.",
    "Saw your shader screenshot — what noise function is that?",
    "Your Rust rewrite numbers are wild. Got a writeup?",
    "Do you take critique requests? I have a portrait set.",
    "Your io_uring link sent me down a rabbit hole, thanks a lot (genuinely).",
]

DM_REPLIES = [
    "Thanks! Happy to chat more about it.",
    "Yeah I'll be there, see you around!",
    "Of course, ask away.",
    "Appreciate it — the community makes it fun.",
    "Simplex with domain warping. I'll post a breakdown.",
    "Working on the blog post now, will send it over.",
    "Sure, send them my way.",
    "Ha! It only gets deeper from there.",
]

DM_FOLLOWUPS = [
    "Also — did you see the pinned post? Relevant to what you asked.",
    "One more thing: check the community rules before posting, mods are thorough.",
    "By the way, your last comment got quoted in another thread.",
    "Sent you the link. Let me know what you think.",
]

REPORT_REASONS = [
    "Spam / self-promotion without context",
    "Harassment in the replies",
    "Off-topic for this community",
    "Misleading title",
    "Unmarked NSFW content",
    "Reposted content from last week",
]


class Command(BaseCommand):
    help = "Populate the database with realistic sample data for local development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing seeded data (users, communities, posts, …) before seeding.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible data (default: 42).",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        rng = random.Random(opts["seed"])

        if opts["flush"]:
            self._flush()

        if User.objects.filter(username="ada").exists() and not opts["flush"]:
            raise CommandError(
                "Seed data already present (user 'ada' exists). "
                "Re-run with --flush to reset, or flush manually."
            )

        users = self._create_users()
        communities = self._create_communities(users, rng)
        posts = self._create_posts(communities, rng)
        comments = self._create_comments(posts, rng)
        self._create_votes(users, posts, rng)
        self._create_follows(users, rng)
        self._create_messages(users, rng)
        self._create_reports(users, posts, comments, rng)
        self._create_saves(users, posts, comments, rng)
        self._create_extra_notifications(posts, comments, rng)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(users)} users, {len(communities)} communities, "
                f"{len(posts)} posts, {len(comments)} comments. "
                f"Login with any username / '{DEFAULT_PASSWORD}'."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Tip: run `python manage.py recalculate_karma` to double-check karma."
            )
        )

    # ------------------------------------------------------------------ flush

    def _flush(self):
        self.stdout.write("Flushing existing seed data…")
        usernames = [u[0] for u in USERS]
        slugs = [c["slug"] for c in COMMUNITIES]
        # Posts/comments/votes/reports/saves cascade from users & communities.
        Community.objects.filter(slug__in=slugs).delete()
        User.objects.filter(username__in=usernames).delete()

    # ------------------------------------------------------------------ users

    def _create_users(self) -> list:
        users = []
        for username, bio in USERS:
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password=DEFAULT_PASSWORD,
                bio=bio,
            )
            users.append(user)
        # A superuser for the Django admin.
        if not User.objects.filter(username="admin").exists():
            admin = User.objects.create_superuser(
                username="admin",
                email="admin@example.com",
                password=DEFAULT_PASSWORD,
                bio="Site administrator.",
            )
            users.append(admin)
        return users

    # ------------------------------------------------------------ communities

    def _create_communities(self, users, rng) -> list:
        communities = []
        for i, spec in enumerate(COMMUNITIES):
            creator = users[i % len(users)]
            community = Community.objects.create(
                slug=spec["slug"],
                name=spec["name"],
                description=spec["description"],
                creator=creator,
                is_nsfw=spec.get("is_nsfw", False),
                requires_approval=spec.get("requires_approval", False),
            )
            for order, rule in enumerate(spec["rules"]):
                CommunityRule.objects.create(community=community, order=order, short=rule)
            flairs = [
                Flair.objects.create(community=community, name=name, color=color)
                for name, color in spec["flairs"]
            ]
            community._flairs = flairs  # stash for post creation

            # A post_save signal already made the creator an admin member.
            # Add a random subset of other users, promoting a couple to moderator.
            others = [u for u in users if u != creator]
            members = rng.sample(others, k=rng.randint(8, min(16, len(others))))
            for j, m in enumerate(members):
                role = Membership.Role.MODERATOR if j < 2 else Membership.Role.MEMBER
                Membership.objects.get_or_create(
                    user=m, community=community, defaults={"role": role}
                )
            community._members = [creator, *members]
            communities.append(community)

        # One banned member somewhere, to exercise the mod tooling.
        first = communities[0]
        banned = first._members[-1]
        Membership.objects.filter(user=banned, community=first).update(is_banned=True)

        return communities

    # ------------------------------------------------------------------ posts

    def _create_posts(self, communities, rng) -> list:
        posts = []
        now = timezone.now()
        by_slug = {c.slug: c for c in communities}

        for slug, seeds in POST_SEEDS.items():
            community = by_slug[slug]
            for i, (kind, title, body) in enumerate(seeds):
                author = rng.choice(community._members)
                flair = rng.choice([None, *community._flairs])
                # In approval-gated communities leave the two newest unapproved
                # so the mod approval queue has content.
                is_approved = not (community.requires_approval and i >= len(seeds) - 2)
                post = Post.objects.create(
                    author=author,
                    community=community,
                    kind=kind,
                    title=title,
                    body=body,
                    url=rng.choice(LINKS) if kind == "link" else "",
                    flair=flair,
                    is_pinned=(i == 0 and rng.random() < 0.5),
                    is_nsfw=community.is_nsfw or rng.random() < 0.03,
                    is_approved=is_approved,
                )
                # Backdate creation so hot/top feeds have a spread.
                Post.objects.filter(pk=post.pk).update(
                    created_at=now - timedelta(hours=rng.randint(1, 24 * 30))
                )
                posts.append(post)

        # Poll posts with options and votes.
        for slug, (title, options) in POLL_SEEDS.items():
            community = by_slug[slug]
            author = rng.choice(community._members)
            post = Post.objects.create(
                author=author,
                community=community,
                kind=Post.Kind.POLL,
                title=title,
                body="Vote below!",
            )
            poll = Poll.objects.create(
                post=post, closes_at=timezone.now() + timedelta(days=rng.randint(2, 14))
            )
            opts = [
                PollOption.objects.create(poll=poll, text=text, order=order)
                for order, text in enumerate(options)
            ]
            n_voters = min(len(community._members), rng.randint(6, 12))
            for voter in rng.sample(community._members, k=n_voters):
                PollVote.objects.create(poll=poll, option=rng.choice(opts), user=voter)
            posts.append(post)

        return posts

    # --------------------------------------------------------------- comments

    def _create_comments(self, posts, rng) -> list:
        comments = []
        for post in posts:
            authors = post.community._members
            top_level = []
            for _ in range(rng.randint(2, 6)):
                body = rng.choice(COMMENTS)
                # Occasionally @mention another member for autocomplete/notification demos.
                if rng.random() < 0.15:
                    body = f"@{rng.choice(authors).username} {body}"
                comment = Comment.objects.create(
                    post=post,
                    author=rng.choice(authors),
                    body=body,
                )
                top_level.append(comment)
                comments.append(comment)
            # Nested replies, up to three levels deep.
            for parent in top_level:
                for _ in range(rng.randint(0, 3)):
                    reply = Comment.objects.create(
                        post=post,
                        author=rng.choice(authors),
                        parent=parent,
                        body=rng.choice(REPLY_COMMENTS),
                    )
                    comments.append(reply)
                    if rng.random() < 0.35:
                        deep = Comment.objects.create(
                            post=post,
                            author=rng.choice(authors),
                            parent=reply,
                            body=rng.choice(REPLY_COMMENTS),
                        )
                        comments.append(deep)
        return comments

    # ------------------------------------------------------------------ votes

    def _create_votes(self, users, posts, rng):
        post_ct = ContentType.objects.get_for_model(Post)
        comment_ct = ContentType.objects.get_for_model(Comment)

        for post in posts:
            voters = rng.sample(users, k=rng.randint(3, len(users)))
            for voter in voters:
                if voter == post.author:
                    continue
                # Weighted toward upvotes.
                value = Vote.UP if rng.random() < 0.8 else Vote.DOWN
                Vote.objects.get_or_create(
                    user=voter,
                    content_type=post_ct,
                    object_id=post.pk,
                    defaults={"value": value},
                )

        for comment in Comment.objects.all():
            voters = rng.sample(users, k=rng.randint(0, 6))
            for voter in voters:
                if voter == comment.author:
                    continue
                value = Vote.UP if rng.random() < 0.75 else Vote.DOWN
                Vote.objects.get_or_create(
                    user=voter,
                    content_type=comment_ct,
                    object_id=comment.pk,
                    defaults={"value": value},
                )

    # ---------------------------------------------------------------- follows

    def _create_follows(self, users, rng):
        follow_ct_targets = []
        for follower in users:
            targets = rng.sample([u for u in users if u != follower], k=rng.randint(2, 8))
            for followed in targets:
                _, created = Follow.objects.get_or_create(follower=follower, followed=followed)
                if created:
                    follow_ct_targets.append((followed, follower))
        # A sampling of follow notifications so inboxes aren't empty.
        user_ct = ContentType.objects.get_for_model(User)
        for followed, follower in rng.sample(follow_ct_targets, k=min(20, len(follow_ct_targets))):
            Notification.objects.create(
                recipient=followed,
                actor=follower,
                verb=Notification.Verb.FOLLOW,
                target_ct=user_ct,
                target_id=follower.pk,
            )

    # --------------------------------------------------------------- messages

    def _create_messages(self, users, rng):
        message_ct = ContentType.objects.get_for_model(Message)
        pairs = set()
        made = 0
        while made < 14:
            a, b = rng.sample(users, k=2)
            key = tuple(sorted((a.id, b.id)))
            if key in pairs:
                continue
            pairs.add(key)
            convo, _ = Conversation.objects.get_or_create(
                participant_a_id=key[0], participant_b_id=key[1]
            )
            first = Message.objects.create(
                conversation=convo, sender=a, body=rng.choice(DM_OPENERS)
            )
            reply = Message.objects.create(
                conversation=convo, sender=b, body=rng.choice(DM_REPLIES)
            )
            # Some conversations get a longer back-and-forth.
            last = reply
            for _ in range(rng.randint(0, 3)):
                sender = a if last.sender == b else b
                last = Message.objects.create(
                    conversation=convo, sender=sender, body=rng.choice(DM_FOLLOWUPS)
                )
            # Mark the opener as read; leave the rest unread for the counter.
            Message.objects.filter(pk=first.pk).update(read_at=timezone.now())
            Notification.objects.create(
                recipient=a,
                actor=b,
                verb=Notification.Verb.DM,
                target_ct=message_ct,
                target_id=reply.pk,
            )
            made += 1

    # ---------------------------------------------------------------- reports

    def _create_reports(self, users, posts, comments, rng):
        post_ct = ContentType.objects.get_for_model(Post)
        comment_ct = ContentType.objects.get_for_model(Comment)
        statuses = (
            [Report.Status.OPEN] * 6 + [Report.Status.RESOLVED] * 2 + [Report.Status.DISMISSED] * 2
        )
        targets = [(post_ct, p) for p in rng.sample(posts, k=min(6, len(posts)))] + [
            (comment_ct, c) for c in rng.sample(comments, k=min(4, len(comments)))
        ]
        for (ct, target), status in zip(targets, statuses, strict=False):
            reporter = rng.choice([u for u in users if u.pk != target.author_id])
            Report.objects.create(
                reporter=reporter,
                content_type=ct,
                object_id=target.pk,
                reason=rng.choice(REPORT_REASONS),
                status=status,
            )

    # ------------------------------------------------------------------ saves

    def _create_saves(self, users, posts, comments, rng):
        post_ct = ContentType.objects.get_for_model(Post)
        comment_ct = ContentType.objects.get_for_model(Comment)
        for user in rng.sample(users, k=min(12, len(users))):
            for post in rng.sample(posts, k=rng.randint(1, 5)):
                SavedItem.objects.get_or_create(user=user, content_type=post_ct, object_id=post.pk)
            for comment in rng.sample(comments, k=rng.randint(0, 3)):
                SavedItem.objects.get_or_create(
                    user=user, content_type=comment_ct, object_id=comment.pk
                )

    # ---------------------------------------------------- extra notifications

    def _create_extra_notifications(self, posts, comments, rng):
        """Comment/reply/mention notifications normally come from the views;
        recreate a sampling here so seeded inboxes look lived-in."""
        comment_ct = ContentType.objects.get_for_model(Comment)
        for comment in rng.sample(comments, k=min(30, len(comments))):
            if comment.parent_id:
                recipient = comment.parent.author
                verb = Notification.Verb.REPLY
            else:
                recipient = comment.post.author
                verb = Notification.Verb.COMMENT
            if recipient.pk == comment.author_id:
                continue
            Notification.objects.create(
                recipient=recipient,
                actor=comment.author,
                verb=verb,
                target_ct=comment_ct,
                target_id=comment.pk,
            )
