"""Social layer: feed across many activities, likes, comments, follows, profiles, posts and
'I'm in too', which turns someone's open plan into a real group with them."""
import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_flow import h


@pytest.fixture()
def client():
    from rally.main import app
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        yield c


def test_feed_spans_many_activities_and_hides_private_prefs(client):
    f = client.get("/v1/feed", headers=h(client, "u_kevin")).json()
    acts = {i["activity"] for i in f["items"]}
    assert len(acts) >= 20 and {"rock_climbing", "surfing", "hot_air_balloon", "pottery"} <= acts
    assert {i["type"] for i in f["items"]} >= {"plan", "post"}
    assert f["trending"][0]["openPlans"] >= 3
    blob = str(f)
    assert "weights" not in blob and "priceWorst" not in blob and "reservation" not in blob
    climbing = client.get("/v1/feed", params={"activity": "rock climbing"}, headers=h(client, "u_kevin")).json()
    assert climbing["items"] and all(i["activity"] == "rock_climbing" for i in climbing["items"])
    following = client.get("/v1/feed", params={"scope": "following"}, headers=h(client, "u_kevin")).json()
    assert {i["user"]["id"] for i in following["items"]} <= {"c_lena", "c_marco", "c_sofia"}


def test_like_comment_follow_and_profile(client):
    c = client
    post = next(i for i in c.get("/v1/feed", headers=h(c, "u_kevin")).json()["items"] if i["type"] == "post")
    liked = c.post(f"/v1/feed/{post['id']}/like", headers=h(c, "u_kevin")).json()
    assert liked["likedByMe"] and liked["likes"] == post["likes"] + 1
    assert c.post(f"/v1/feed/{post['id']}/like", headers=h(c, "u_kevin")).json()["likes"] == post["likes"]
    cm = c.post(f"/v1/feed/{post['id']}/comments", json={"text": "Which shop?"}, headers=h(c, "u_ana")).json()
    assert cm[-1]["user"]["name"] == "Ana" and cm[-1]["text"] == "Which shop?"
    assert c.post(f"/v1/feed/{post['id']}/comments", json={"text": "  "}, headers=h(c, "u_ana")).status_code == 422
    fol = c.post("/v1/people/c_ben/follow", headers=h(c, "u_kevin")).json()
    assert fol["following"] is True
    prof = c.get("/v1/people/c_ben", headers=h(c, "u_kevin")).json()
    assert prof["followedByMe"] and prof["bio"] and prof["plans"][0]["activity"] == "rock_climbing"
    assert {"activity": "rock_climbing", "label": "Rock climbing"} in prof["interests"]
    assert c.post("/v1/people/u_kevin/follow", headers=h(c, "u_kevin")).status_code == 422
    found = c.get("/v1/people", params={"q": "climb"}, headers=h(c, "u_kevin")).json()
    assert {"c_lena", "c_ben"} <= {p["id"] for p in found}
    me = c.post("/v1/posts", json={"text": "Anyone up for pickleball Sunday?", "activity": "pickleball"},
                headers=h(c, "u_kevin")).json()
    assert me["activityLabel"] == "Pickleball" and me["user"]["id"] == "u_kevin"
    assert c.post("/v1/posts", json={"text": "recap", "dealId": "d_nope"}, headers=h(c, "u_kevin")).status_code in (403, 404)   # only people who went can recap


def test_im_in_too_turns_a_plan_into_a_group(client):
    c = client
    plan = next(i for i in c.get("/v1/feed", params={"activity": "rock_climbing"}, headers=h(c, "u_kevin")).json()["items"]
                if i["type"] == "plan" and i["user"]["id"] == "c_lena")
    r = c.post(f"/v1/feed/plans/{plan['id']}/join", headers=h(c, "u_kevin"))
    assert r.status_code == 200, r.text
    j = r.json()
    goal = c.get(f"/v1/goals/{j['goalId']}", headers=h(c, "u_kevin")).json()
    assert goal["status"] == "published" and goal["draft"]["activity"] == "rock_climbing"
    m = c.post(f"/v1/intents/{j['intentId']}/matches", json={}, headers=h(c, "u_kevin")).json()
    names = {x["name"] for x in m["matches"]}
    assert "Lena Park" in names and "Ben Carter" in names            # other Yosemite climbers too
    assert "Marco Rossi" not in names                                 # surfer, not a climber
    deal = c.post("/v1/deals", json={"intentId": j["intentId"], "candidateIntentIds": [plan["id"]]},
                  headers=h(c, "u_kevin")).json()
    assert deal["activity"] == "rock_climbing" and deal["groupMax"] >= 2
    assert c.post(f"/v1/feed/plans/{j['intentId']}/join", headers=h(c, "u_kevin")).status_code in (404, 422)
