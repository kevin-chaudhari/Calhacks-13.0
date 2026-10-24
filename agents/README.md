# Agents

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Rally runs 27 uAgents. Every identity comes from `AGENT_SEED_PREFIX`, so the API and the agents process derive the same addresses without asking the network.

| Agent | Count | Where it runs | What it does |
|---|---|---|---|
| Group mediator | 1 | inside the API (FastAPI lifespan) | Sends `PlanSpaceWire` / `ProposalWire`, takes `ResponseWire`; the only agent that writes through `service.py` |
| Personal agents | 20 (one per person) | `agents/run_agents.py` | Hold their owner's private prefs per goal; answer with accept, one change request, or a hard no |
| Provider agents | 6 (one per vendor) | `agents/run_agents.py` | Answer `QuoteRequestWire` from `data/fixtures/providers.json` |

| Rally concierge | 1 | `agents/concierge.py` | Chat Protocol agent for ASI:One: a typed goal becomes a negotiated group plan with a room link |

Shared code: `services/api/rally/negotiation/` has `wire.py` (message models), `network.py` (seeds, ports, agent factory) and `transport.py` (`UAgentsTransport`, same interface as `InProcTransport`).

## Run it over the network

```bash
pip install uagents uagents-core        # tested with uagents 0.26.1

# Local, no Fetch.ai account: real uAgents messages over HTTP on localhost
AGENT_NETWORK=local python agents/run_agents.py                     # terminal 1
TRANSPORT=agentverse AGENT_NETWORK=local python scripts/rally.py dev # terminal 2
TRANSPORT=agentverse AGENT_NETWORK=local python -m pytest tests/integration/test_transport_agentverse.py

# Agentverse mailboxes (set a private AGENT_SEED_PREFIX and AGENTVERSE_API_KEY in .env first)
python agents/run_agents.py                                         # terminal 1
TRANSPORT=agentverse python scripts/rally.py dev                    # terminal 2
python agents/connect_agentverse.py                                 # once: registers the 8 Agentverse agents
```

With `TRANSPORT=agentverse` the UI badge reads "Agents: agentverse" only once the mediator agent is actually up; if it fails to start, the API stays in-process and says "inproc".

Goals typed live in the app (not in the fixtures) reach their owner's agent as one `PrefsWire` from the API, which received them from the owner's browser, just before the plan space. The mediator logic never reads them.

`bureau_demo.py` runs the same negotiation in a single local Bureau, using the same `UAgentsTransport`:

```bash
python agents/bureau_demo.py     # agreed on v4 in 4 rounds, ~1 ms per hop on one machine
```

## Rally on ASI:One (concierge)

`agents/concierge.py` speaks the Chat Protocol (`ChatMessage` / `ChatAcknowledgement`, manifest published) through an Agentverse mailbox, so ASI:One can route a goal to it. For each goal it calls the Rally API (compile → answer a missing question → publish → matches → deal → negotiate → poll the snapshot) and replies in three messages: what Rally understood, who matched and who didn't (with reasons), and the agreed plan with the price per person and a link to `RALLY_WEB_URL/deals/<id>`.

```bash
python agents/concierge.py        # needs RALLY_API_URL, RALLY_WEB_URL; mailbox via connect_agentverse.py
```

```
You:   Scuba in Monterey next month under $300, I'm Open Water.
Rally: How many people at most, including you? (for example 4, 5, 6)
You:   5
Rally: Here's what I understood: Scuba diving, near Monterey, CA, Nov 1–Nov 30, up to $300 per person, ...
Rally: Found 4 people who fit: Ana, Maya, Kai, Eli. Not a fit: Luis (Only free Dec 19–Dec 31); ...
Rally: Agreed! All 5 agents accepted plan v3 in 3 rounds: Nov 21, boat dive, gear included, Lovers Point
       with Kelp Line Divers, $199 per person (simulated quote). Everyone approves in the group room: <link>
```

**Identity (demo):** ASI:One senders map to `CONCIERGE_PERSONAS` in order of first contact. By default that is only `u_kevin`, so **the first sender (and every sender) acts as Kevin**. Say "start over" to drop a half-finished goal.

**Repeat runs:** people already in a deal aren't matched again, so a second chat finds nobody until the board is reset. Set `CONCIERGE_RESET_EACH_GOAL=1` for judging; it resets the scuba scenario before each new goal (earlier rooms end).

Tests: `tests/unit/test_concierge.py` (fake API: the three replies, the follow-up question, errors) and `tests/integration/test_concierge_api.py` (the real API in-process).

## Group changes (for the room UI)

**Group-size nudge.** After its binding quote, the provider agent checks the next tier for the same plan. If one more person lowers the price, the group is below `groupMax`, and a stored match is free, it sends a `NudgeMsg` and the deal carries:

```json
"nudge": {"providerId": "p_kelpline", "extraPeople": 1, "newPricePerPerson": 139.0, "savingPerPerson": 15.0}
```

`POST /v1/deals/{id}/nudge/accept` (organizer only) invites the best-ranked free match, voids approvals and renegotiates; it returns `{"invitedUserId": "u_eli", "status": "NEGOTIATING"}`. Errors: `403 ORGANIZER_ONLY`, `409 NO_NUDGE`, `409 NO_MATCH`. `nudge` is `null` again once negotiation restarts.

**Auto-replace.** When a member leaves during negotiation or approval and a stored match is free, the mediator invites them so the group keeps its size, and records `"replacements": [{"leftUserId": "u_ana", "invitedUserId": "u_eli", "at": 1792870000000}]` plus a `member.replaced` event. Without a free match it renegotiates with fewer people, as before.

## Addresses

Generated with `python agents/connect_agentverse.py --table` from the team's private `AGENT_SEED_PREFIX`. Agentverse's free plan holds 8 agents per account, so the 8 that judges meet (the ASI:One concierge, the mediator, the scuba demo group and its vendor) have mailboxes and Agentverse pages; the other 20 run as plain uAgents reached by direct HTTP. Change the set with `AGENTVERSE_AGENTS`.

| Agent | Kind | Address | Agentverse |
|---|---|---|---|
| Rally · group mediator | mediator | `agent1qvscamdczpsks92damhtxuesuhcaj3e78f0eva7rqt6w5d6lhw6agzw23q9` | [profile](https://agentverse.ai/agents/details/agent1qvscamdczpsks92damhtxuesuhcaj3e78f0eva7rqt6w5d6lhw6agzw23q9/profile) |
| Rally · Kevin's agent | personal | `agent1qv2wrayq80ve4z5x0uyj4phmlwgdm9p282sqw878zy723mmjgezfcm000v7` | [profile](https://agentverse.ai/agents/details/agent1qv2wrayq80ve4z5x0uyj4phmlwgdm9p282sqw878zy723mmjgezfcm000v7/profile) |
| Rally · Ana's agent | personal | `agent1qw2kn973ht957clt7cwlm522x9mpns7943xs55c5wtp6ryp69f6ag0afunj` | [profile](https://agentverse.ai/agents/details/agent1qw2kn973ht957clt7cwlm522x9mpns7943xs55c5wtp6ryp69f6ag0afunj/profile) |
| Rally · Ravi's agent | personal | `agent1qfvhtemr8sy5z6ah2wzlg4cxwywz4ec5djn59t87gep205autcuqc45vq6n` | [profile](https://agentverse.ai/agents/details/agent1qfvhtemr8sy5z6ah2wzlg4cxwywz4ec5djn59t87gep205autcuqc45vq6n/profile) |
| Rally · Maya's agent | personal | `agent1qga4kq5c262hfdzq52f96g8rngwhxpgcfxfg56gdvtcgcqwefr7yywsaw0k` | [profile](https://agentverse.ai/agents/details/agent1qga4kq5c262hfdzq52f96g8rngwhxpgcfxfg56gdvtcgcqwefr7yywsaw0k/profile) |
| Rally · Kai's agent | personal | `agent1qw327s826z9gp5cpaghg4zmley0er7uxjkx4uc0e9508mzcfh8kxyjra9hl` | [profile](https://agentverse.ai/agents/details/agent1qw327s826z9gp5cpaghg4zmley0er7uxjkx4uc0e9508mzcfh8kxyjra9hl/profile) |
| Rally · Eli's agent | personal | `agent1qtduus7g2l9xx0dp0lt6qgp9ll5nqrcg9kxw5aap75sdfzdj6yjlxyc0fhk` | local uAgent (not registered) |
| Rally · Luis's agent | personal | `agent1qtta67ur7xfdk04xacvk9heq6knn284t55m5vafcngq2je0e9uvncht8yy4` | local uAgent (not registered) |
| Rally · Sam's agent | personal | `agent1qwwnr40grs8ah873ve6mgdjqrndgekfq4wz2d4fvyltrpzvuytcfg4a3aax` | local uAgent (not registered) |
| Rally · Priya's agent | personal | `agent1qdljljlnvk57vff5q9uwpzyrajrxx7fna8wnxj939ju4dnqxelp4uepqqp0` | local uAgent (not registered) |
| Rally · Theo's agent | personal | `agent1qdre45eguffavyq0zmkw9se3s8xky4tt25aaqauugnmem9hnr6485lkfa46` | local uAgent (not registered) |
| Rally · Noor's agent | personal | `agent1q2vlece25uw62dul9a64lc9kdpl56kgth874nrgmsa9shxp5600yjr75u97` | local uAgent (not registered) |
| Rally · Jordan's agent | personal | `agent1qtvcx6yepma6ngpqmwg3fydw055xmgr0q40pa37hqm6wfe5u86ttv8g7553` | local uAgent (not registered) |
| Rally · Mei's agent | personal | `agent1q0snzpedfggdjapy4w2ya78h5lnwrwytpzpzzwnvxhqf3k6xnzlyuzehpfy` | local uAgent (not registered) |
| Rally · Tomas's agent | personal | `agent1qf2u43jw87wg4pr4aa2yxqvcc06qlluwnl3jar5wcpga5sj95457vp75dty` | local uAgent (not registered) |
| Rally · Owen's agent | personal | `agent1qgapas7n5u2lrsdtpjremzeyedk6pnzm7aalym6tquxqz9ps9skpg3mu75e` | local uAgent (not registered) |
| Rally · Lucia's agent | personal | `agent1q0xgarwk6fsnjft7j2rp79dtw0gd7x4a7g4d5qe8fzpl8fhempg4u6a5x3l` | local uAgent (not registered) |
| Rally · Dev's agent | personal | `agent1qd5zl5qvdnhz9dv4y0cg5wcqrcq2ej2vnd8889qdepdc9g0ta9q9wsphvak` | local uAgent (not registered) |
| Rally · Hana's agent | personal | `agent1q0unkq9nxr4pua3vrsmpu55np9pezh46z77lfkuj285p3z56n2j0jszaelz` | local uAgent (not registered) |
| Rally · Felix's agent | personal | `agent1qwvc08pgje6327avq7fn82p83czldvgy5fhtk3f374yd4zanmm55x5eqxvh` | local uAgent (not registered) |
| Rally · Zara's agent | personal | `agent1qt40lhur2mrlaenutg4ecrfsj54cjrwqwp0vdre4tqpr89mvr66ggllxr7p` | local uAgent (not registered) |
| Rally · Kelp Line Divers | provider | `agent1qwzus3gqxu60fejyd2ek4escdazzcg4nt06q2976zl9wcwsqc6lrupkc27r` | local uAgent (not registered) |
| Rally · Otter Cove Dive Co. | provider | `agent1qtprw9vtn0u9gytcgzswy6ye34g2emrgne9uux5ru9m7v80xfj93jjj423x` | [profile](https://agentverse.ai/agents/details/agent1qtprw9vtn0u9gytcgzswy6ye34g2emrgne9uux5ru9m7v80xfj93jjj423x/profile) |
| Rally · Pacific Freefall | provider | `agent1q0nt6afcc7sp0uf7wvjtf2txg5a33q333m56naetyvk03ykq289d5pe062n` | local uAgent (not registered) |
| Rally · Redwood Skydive Co. | provider | `agent1qvft3d56k5ly699g3zua9tg2yqpz56eknflfxkmu977dk04nkmstypvj6uy` | local uAgent (not registered) |
| Rally · Harbor Paddle Co. | provider | `agent1qfyc58vgaqu0lgnpk0eege47kwkprd92tdkvr74kdv0g24sehdr8servd69` | local uAgent (not registered) |
| Rally · Stillwater Kayak Tours | provider | `agent1qv2txz7fg6tfy0aq966jslg39g7vfnfyuracqg2zhdr90jceqnp7cj3akpl` | local uAgent (not registered) |
| Rally concierge | concierge | `agent1qv97ccelftm7tv4gz523jgzehqq0tz0h6mxc2v2gu43jx7elke5hwhe2ca6` | [profile](https://agentverse.ai/agents/details/agent1qv97ccelftm7tv4gz523jgzehqq0tz0h6mxc2v2gu43jx7elke5hwhe2ca6/profile) |

Measured on Oct 24 (scuba, 5 members over Agentverse mailboxes): plan v4 in 4 rounds, the same as in-process; replies took 3.5–7.8 s per hop, 56 s end to end including the 1.4 s per-round demo pacing. `AGENT_DIRECT=1` sends between Rally's own agents by direct HTTP instead (milliseconds) when the venue network is slow.

## Not done yet

- Provider agents run and answer `QuoteRequestWire`, but the API still prices quotes from its own copy of the vendor sheets (so vendor edits in the portal apply); the price-sheet request is not yet sent over the network.
- Invites and joins (`InviteMsg` / `JoinMsg`) are still decided in the API.
