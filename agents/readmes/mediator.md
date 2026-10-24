# Rally group mediator

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Negotiates **one shared plan** for a group of Rally personal agents, using a bounded single-negotiating-text loop.

- Every plan it proposes satisfies every member's known hard constraints (0 violations in 50 evaluated negotiations).
- Stops within a fixed round budget; reports agreement only when every active member accepted the exact same version.
- Never sees anyone's private preferences: members reveal at most one term per round.
- Drops any response whose sender address does not own the member it claims to be.
