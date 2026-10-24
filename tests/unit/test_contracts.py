"""Shared contract fields agreed in the team plan (chore/contracts)."""
from rally_contracts import Deal, DealStatus, Nudge, NudgeMsg, Replacement


def test_deal_defaults_keep_old_snapshots_valid():
    d = Deal(id="d", shape="group_provider", activity="scuba_diving", title="t", status=DealStatus.NEGOTIATING,
             deadline_at=0, created_by="u", created_at=0)
    w = d.wire()
    assert w["nudge"] is None and w["replacements"] == [] and w["negotiationMs"] is None


def test_nudge_and_replacement_wire_names_are_camel_case():
    n = Nudge(provider_id="p", extra_people=1, current_price_per_person=179, new_price_per_person=154,
              saving_per_person=25)
    assert set(n.wire()) >= {"providerId", "extraPeople", "currentPricePerPerson", "newPricePerPerson",
                             "savingPerPerson", "status"}
    r = Replacement(left_user_id="u_ana", invited_user_id="u_eli", at=1)
    assert r.wire()["leftUserId"] == "u_ana"
    m = NudgeMsg(msg_id="m", deal_id="d", provider_id="p", proposal_version=4, group_size=4, extra_people=1,
                 current_price_per_person=179, new_price_per_person=154)
    assert NudgeMsg.model_validate(m.wire()) == m
