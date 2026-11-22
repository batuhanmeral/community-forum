import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.modmail.models import ModmailMessage, ModmailThread
from apps.notifications.models import Notification
from apps.social.models import Block

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def world():
    names = ("admin", "mod", "user", "other")
    users = {
        n: User.objects.create_user(username=n, email=f"{n}@example.test", password="x")
        for n in names
    }
    community = Community.objects.create(slug="mm", name="MM", creator=users["admin"])
    Membership.objects.create(user=users["mod"], community=community, role="moderator")
    Membership.objects.create(user=users["user"], community=community)
    return users, community


def client(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


def open_thread(users, community, subject="Help", body="Please help"):
    response = client(users["user"]).post(
        f"/api/v1/communities/{community.slug}/modmail/", {"subject": subject, "body": body}
    )
    assert response.status_code == 201, response.data
    return response.data["id"]


def test_user_opens_thread_and_mods_are_notified(world):
    users, community = world
    thread_id = open_thread(users, community)
    thread = ModmailThread.objects.get(pk=thread_id)
    assert thread.creator == users["user"] and thread.status == "open"
    assert thread.messages.get().body == "Please help"
    for mod in ("admin", "mod"):
        assert Notification.objects.filter(recipient=users[mod], verb="modmail").exists()
    assert not Notification.objects.filter(recipient=users["user"], verb="modmail").exists()


def test_banned_user_and_non_member_can_open_threads(world):
    users, community = world
    Membership.objects.filter(user=users["user"]).update(is_banned=True)
    assert (
        client(users["user"])
        .post(
            f"/api/v1/communities/{community.slug}/modmail/",
            {"subject": "Ban appeal", "body": "Sorry"},
        )
        .status_code
        == 201
    )
    assert (
        client(users["other"])
        .post(f"/api/v1/communities/{community.slug}/modmail/", {"subject": "Q", "body": "Hi"})
        .status_code
        == 201
    )


def test_anonymous_cannot_open_and_validation(world):
    users, community = world
    url = f"/api/v1/communities/{community.slug}/modmail/"
    assert client().post(url, {"subject": "x", "body": "y"}).status_code in (401, 403)
    api = client(users["user"])
    assert api.post(url, {"subject": "", "body": "y"}).status_code == 400
    assert api.post(url, {"subject": "s" * 101, "body": "y"}).status_code == 400
    assert api.post(url, {"subject": "s", "body": "b" * 5001}).status_code == 400
    assert api.post(url, {"subject": "s", "body": ""}).status_code == 400


def test_five_new_threads_per_day_per_community(world):
    users, community = world
    for i in range(5):
        open_thread(users, community, subject=f"T{i}")
    response = client(users["user"]).post(
        f"/api/v1/communities/{community.slug}/modmail/", {"subject": "6", "body": "x"}
    )
    assert response.status_code == 429
    other = Community.objects.create(slug="mm2", name="MM2", creator=users["admin"])
    assert (
        client(users["user"])
        .post(f"/api/v1/communities/{other.slug}/modmail/", {"subject": "ok", "body": "x"})
        .status_code
        == 201
    )


def test_only_participants_and_mods_can_read_a_thread(world):
    users, community = world
    thread_id = open_thread(users, community)
    url = f"/api/v1/modmail/{thread_id}/"
    for name, expected in (("user", 200), ("mod", 200), ("admin", 200), ("other", 404)):
        assert client(users[name]).get(url).status_code == expected
    assert client().get(url).status_code in (401, 403)
    assert client(users["other"]).get(url + "messages/").status_code == 404
    assert client(users["other"]).post(url + "messages/", {"body": "hi"}).status_code == 404


def test_mod_from_another_community_has_no_access(world):
    users, community = world
    thread_id = open_thread(users, community)
    elsewhere = Community.objects.create(slug="else", name="Else", creator=users["other"])
    assert client(users["other"]).get(f"/api/v1/modmail/{thread_id}/").status_code == 404
    assert elsewhere  # other is an admin of another community only


def test_banned_moderator_loses_access(world):
    users, community = world
    thread_id = open_thread(users, community)
    Membership.objects.filter(user=users["mod"]).update(is_banned=True)
    assert client(users["mod"]).get(f"/api/v1/modmail/{thread_id}/").status_code == 404


def test_internal_notes_never_reach_the_creator(world):
    users, community = world
    thread_id = open_thread(users, community)
    mod = client(users["mod"])
    url = f"/api/v1/modmail/{thread_id}/messages/"
    assert mod.post(url, {"body": "secret plan", "is_internal": True}).status_code == 201
    assert mod.post(url, {"body": "public reply"}).status_code == 201
    creator_view = client(users["user"]).get(url).data["results"]
    assert [m["body"] for m in creator_view] == ["Please help", "public reply"]
    assert all("is_internal" not in m or m["is_internal"] is False for m in creator_view)
    mod_view = mod.get(url).data["results"]
    assert [m["body"] for m in mod_view] == ["Please help", "secret plan", "public reply"]
    # No notification (and so no leak) for an internal note.
    assert Notification.objects.filter(recipient=users["user"], verb="modmail").count() == 1


def test_creator_cannot_post_internal_notes(world):
    users, community = world
    thread_id = open_thread(users, community)
    response = client(users["user"]).post(
        f"/api/v1/modmail/{thread_id}/messages/", {"body": "x", "is_internal": True}, format="json"
    )
    assert response.status_code in (400, 403)
    assert ModmailMessage.objects.filter(thread_id=thread_id).count() == 1


def test_creator_does_not_see_which_moderator_replied(world):
    users, community = world
    thread_id = open_thread(users, community)
    client(users["mod"]).post(f"/api/v1/modmail/{thread_id}/messages/", {"body": "hello"})
    reply = client(users["user"]).get(f"/api/v1/modmail/{thread_id}/messages/").data["results"][1]
    assert reply["author_username"] is None and reply["from_moderator"] is True
    mod_reply = (
        client(users["admin"]).get(f"/api/v1/modmail/{thread_id}/messages/").data["results"][1]
    )
    assert mod_reply["author_username"] == "mod"
    detail = client(users["user"]).get(f"/api/v1/modmail/{thread_id}/").data
    assert "assigned_to" not in detail and "assigned_to_username" not in detail


def test_mod_reply_notifies_creator_and_user_reply_notifies_assignee_only(world):
    users, community = world
    thread_id = open_thread(users, community)
    Notification.objects.all().delete()
    mod = client(users["mod"])
    assert (
        mod.patch(f"/api/v1/modmail/{thread_id}/", {"assigned_to": users["mod"].pk}).status_code
        == 200
    )
    mod.post(f"/api/v1/modmail/{thread_id}/messages/", {"body": "on it"})
    assert Notification.objects.filter(recipient=users["user"], verb="modmail").count() == 1
    Notification.objects.all().delete()
    client(users["user"]).post(f"/api/v1/modmail/{thread_id}/messages/", {"body": "thanks"})
    assert Notification.objects.filter(verb="modmail").count() == 1
    assert Notification.objects.get(verb="modmail").recipient == users["mod"]


def test_unassigned_user_reply_notifies_all_mods_respecting_mute(world):
    users, community = world
    Membership.objects.filter(user=users["mod"]).update(notify_level="off")
    thread_id = open_thread(users, community)
    assert not Notification.objects.filter(recipient=users["mod"], verb="modmail").exists()
    assert Notification.objects.filter(recipient=users["admin"], verb="modmail").exists()
    assert thread_id


def test_mod_who_blocked_the_user_is_not_notified(world):
    users, community = world
    Block.objects.create(blocker=users["mod"], blocked=users["user"])
    open_thread(users, community)
    assert not Notification.objects.filter(recipient=users["mod"], verb="modmail").exists()
    assert Notification.objects.filter(recipient=users["admin"], verb="modmail").exists()


def test_assignment_archive_and_reopen(world):
    users, community = world
    thread_id = open_thread(users, community)
    url = f"/api/v1/modmail/{thread_id}/"
    mod = client(users["mod"])
    assert client(users["user"]).patch(url, {"status": "archived"}).status_code == 403
    assert mod.patch(url, {"assigned_to": users["user"].pk}).status_code == 400  # not a mod
    assert mod.patch(url, {"assigned_to": users["admin"].pk}).status_code == 200
    assert mod.patch(url, {"assigned_to": None}, format="json").status_code == 200
    assert mod.patch(url, {"status": "archived"}).status_code == 200
    assert ModmailThread.objects.get(pk=thread_id).status == "archived"
    # A reply from the creator reopens the thread.
    client(users["user"]).post(url + "messages/", {"body": "one more thing"})
    assert ModmailThread.objects.get(pk=thread_id).status == "open"


def test_message_cap_per_thread(world, settings):
    users, community = world
    thread_id = open_thread(users, community)
    ModmailMessage.objects.bulk_create(
        [ModmailMessage(thread_id=thread_id, author=users["user"], body="x") for _ in range(299)]
    )
    response = client(users["user"]).post(
        f"/api/v1/modmail/{thread_id}/messages/", {"body": "over"}
    )
    assert response.status_code == 400


def test_lists_inbox_and_mine(world):
    users, community = world
    a = open_thread(users, community, subject="A")
    b = open_thread(users, community, subject="B")
    client(users["mod"]).patch(f"/api/v1/modmail/{b}/", {"status": "archived"})
    inbox = f"/api/v1/communities/{community.slug}/modmail/"
    mod = client(users["mod"])
    assert [t["id"] for t in mod.get(inbox).data["results"]] == [a]
    assert {t["id"] for t in mod.get(inbox + "?status=archived").data["results"]} == {b}
    assert client(users["user"]).get(inbox).status_code == 403
    mine = client(users["user"]).get("/api/v1/modmail/mine/").data["results"]
    assert {t["id"] for t in mine} == {a, b}
    assert client(users["other"]).get("/api/v1/modmail/mine/").data["results"] == []


def test_lists_do_not_n_plus_one(world, django_assert_max_num_queries):
    users, community = world
    for i in range(8):
        thread = ModmailThread.objects.create(
            community=community, creator=users["user"], subject=f"T{i}"
        )
        ModmailMessage.objects.create(thread=thread, author=users["user"], body="x")
    with django_assert_max_num_queries(9):
        response = client(users["mod"]).get(f"/api/v1/communities/{community.slug}/modmail/")
        assert len(response.data["results"]) == 8


def test_unread_counts_and_mark_read(world):
    users, community = world
    thread_id = open_thread(users, community)
    counts = lambda u: client(users[u]).get("/api/v1/users/me/unread-counts/").data["modmail"]  # noqa: E731
    assert counts("mod") == 1 and counts("user") == 0
    client(users["mod"]).post(f"/api/v1/modmail/{thread_id}/read/")
    assert counts("mod") == 0
    client(users["mod"]).post(f"/api/v1/modmail/{thread_id}/messages/", {"body": "hi"})
    assert counts("user") == 1 and counts("admin") == 1  # admin never read it
    client(users["user"]).get(f"/api/v1/modmail/{thread_id}/messages/")
    client(users["user"]).post(f"/api/v1/modmail/{thread_id}/read/")
    assert counts("user") == 0


def test_internal_note_does_not_make_creator_unread(world):
    users, community = world
    thread_id = open_thread(users, community)
    client(users["mod"]).post(
        f"/api/v1/modmail/{thread_id}/messages/", {"body": "n", "is_internal": True}
    )
    assert client(users["user"]).get("/api/v1/users/me/unread-counts/").data["modmail"] == 0
    assert thread_id


def test_deleted_creator_is_anonymised(world):
    users, community = world
    thread_id = open_thread(users, community)
    User.objects.filter(pk=users["user"].pk).update(is_active=False, username="deleted-1")
    detail = client(users["mod"]).get(f"/api/v1/modmail/{thread_id}/").data
    assert detail["creator_username"] is None
    first = client(users["mod"]).get(f"/api/v1/modmail/{thread_id}/messages/").data["results"][0]
    assert first["author_username"] is None


def test_account_export_includes_authored_modmail_messages(world):
    from apps.users.services import export_account

    users, community = world
    thread_id = open_thread(users, community, body="my appeal")
    client(users["mod"]).post(f"/api/v1/modmail/{thread_id}/messages/", {"body": "mod words"})
    client(users["mod"]).post(
        f"/api/v1/modmail/{thread_id}/messages/", {"body": "secret", "is_internal": True}
    )
    data = export_account(users["user"])
    assert [m["body"] for m in data["modmail_messages"]] == ["my appeal"]
    mod_export = export_account(users["mod"])
    assert [m["body"] for m in mod_export["modmail_messages"]] == ["mod words", "secret"]


def test_realtime_event_published_to_participants(world, monkeypatch):
    users, community = world
    events = []
    monkeypatch.setattr(
        "apps.modmail.services.publish_to_user", lambda uid, event: events.append((uid, event))
    )
    thread_id = open_thread(users, community)
    recipients = {
        uid for uid, e in events if e == {"type": "modmail.updated", "thread_id": thread_id}
    }
    assert users["mod"].pk in recipients and users["admin"].pk in recipients


def test_internal_notes_do_not_wake_the_creator_or_bump_their_view(world, monkeypatch):
    users, community = world
    thread_id = open_thread(users, community)
    before = ModmailThread.objects.get(pk=thread_id).updated
    events = []
    monkeypatch.setattr(
        "apps.modmail.services.publish_to_user", lambda uid, event: events.append(uid)
    )
    client(users["mod"]).post(
        f"/api/v1/modmail/{thread_id}/messages/", {"body": "n", "is_internal": True}
    )
    assert users["user"].pk not in events
    assert users["admin"].pk in events  # the team is still told
    assert ModmailThread.objects.get(pk=thread_id).updated == before


@pytest.mark.django_db(transaction=True)
def test_daily_cap_holds_under_concurrency(world):
    import threading

    from django.db import connection

    from apps.modmail.services import create_thread

    users, community = world
    results = []

    def attempt(i):
        try:
            create_thread(users["user"], community, f"T{i}", "x")
            results.append("ok")
        except Exception as exc:
            results.append(type(exc).__name__)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert ModmailThread.objects.filter(creator=users["user"]).count() == 5
    assert results.count("ok") == 5
