# Deploying Rally (owner: Kevin)

Web on Vercel, API + agents on a Vultr VM behind Caddy (HTTPS), live state in Convex.

## 1. Convex (5 min)
```bash
npx convex dev --once                 # creates the deployment, pushes convex/
npx convex env set RALLY_SERVER_KEY "$(openssl rand -hex 32)"
npx convex env set RALLY_SECRET     "<same value as RALLY_SECRET in .env>"
npx convex deploy                     # production deployment for the demo
```
Put the deployment URL in `CONVEX_URL` (API) and `NEXT_PUBLIC_CONVEX_URL` (web), and the same
`RALLY_SERVER_KEY` in the API's `.env`. Set `STORE=convex`.

## 2. Vultr VM (10 min)
1. Create an Ubuntu 24.04 instance (1 vCPU / 2 GB is enough) and paste `infra/cloud-init.yaml` as user data.
2. Point a DNS A record (e.g. `api.yourteam.dev`) at the VM's IP.
3. `ssh root@IP`, fill `/opt/rally/.env` from `.env.example`. Required for the public demo:
   `CORS_ORIGINS=https://<your-vercel-app>.vercel.app`, `RALLY_WEB_URL=` the same, a fresh `RALLY_SECRET`.
4. `cd /opt/rally && API_DOMAIN=api.yourteam.dev docker compose -f infra/docker-compose.yml up -d --build`
5. `curl https://api.yourteam.dev/v1/health` shows each adapter live or fallback.

Restart safety: `docker compose restart api` keeps every group (Convex dump + agent vault in the
`rally-data` volume); in-flight negotiations resume and log `deal.resumed`.

No Docker? Use `infra/systemd/*.service` with a venv in `/opt/rally/.venv` and Caddy from apt
(set `UPSTREAM=127.0.0.1:8000`).

## 3. Vercel (5 min)
Import the repo, root directory `apps/web`. Environment:
`NEXT_PUBLIC_API_URL=https://api.yourteam.dev`, `NEXT_PUBLIC_CONVEX_URL=…`,
`NEXT_PUBLIC_RALLY_AGENT_ADDRESS=agent1…` (Parikshit's concierge, enables the ASI:One card).

## 4. x402 testnet deposits (optional, 10 min)
```bash
python scripts/x402_wallets.py        # prints X402_PAY_TO, X402_PAYER_KEYS and faucet addresses
```
Fund each payer address with Base Sepolia test USDC at https://faucet.circle.com, paste the lines
into `.env`, set `PAYMENTS=x402_testnet`, restart. Mainnet network names refuse to start.

## Before judging
- Open `/demo` on the projector: all six lights, then "Reset everything".
- `ALLOW_DEMO_ROUTES=1` is needed for the control room and seats; set it to 0 after the event.
- Seat QR codes use `RALLY_WEB_URL`, so it must be the public Vercel URL, not localhost.
