# Rally personal agent

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

One person's agent in Rally, the app that turns a shared goal ("scuba in Monterey next month under $300") into a booked group deal.

- Holds its owner's **private** trip preferences (weights, favourite dates and sites). They never leave this agent.
- Answers the Rally mediator's proposals with one word: **accept**, a **change request** naming one term and one public option, or a **hard no** on one term.
- Concedes over rounds on a fixed curve, so a group converges in a few rounds.

Protocol: `PlanSpaceWire` → `ProposalWire` → `ResponseWire`. Only accepts negotiation messages from the Rally mediator's address.
