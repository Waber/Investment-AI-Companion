# Hosting options for Investment-AI-Companion (post-demo)

*Researcher, 2026-10-08 (Europe/Warsaw). For issues #56 (deployment), #48 (auth) and #58 (scanner); requirements in `docs/product-requirements.md` v0.3, §12 and §8. Read-only research. The repo was not modified.*

## TL;DR

- **Primary: a small EU VPS running Docker Compose** (Caddy or Tailscale for HTTPS → FastAPI → PostgreSQL, plus a scanner container or systemd timer). The pick is **Hetzner Cloud CX23** (2 vCPU / 4 GB / 40 GB, Germany or Finland) with Hetzner daily backups and nightly **encrypted `pg_dump` to a Hetzner Storage Box in a different location**. That's about **€10.29 net, €12.65 / ~55 PLN gross a month**, or ~38 PLN gross without the Storage Box.
  - **Cheaper equivalent: OVH VPS-1 in Warsaw**, 20.07 PLN gross a month with a daily backup included. Add an off-site backup target on top.
- **Fallback (if Raul doesn't want to run Linux): Render in Frankfurt.** Starter web service ($7) + Postgres basic-256mb ($6, 3-day PITR) + one cron job (min $1) is about **$14 net, ~€15.4 / ~67 PLN gross**. TLS, backups and encryption at rest are managed.
- **Avoid free tiers for the real (private) data.** Render Free sleeps after 15 min and its Postgres expires after 30 days. Supabase Free pauses after a week and has no backups. The Koyeb free plan is closed to new users. Oracle's Always Free tier can reclaim idle VMs. Neon Free is the only free DB that fits technically, with limits.
- **Home Raspberry Pi + Tailscale** has the lowest running cost (~4–8 PLN/month electricity, *estimate*) and stays physically private. But it needs ~500–900 PLN of hardware up front (*estimate*), and Raul's home internet and power become the uptime.

## Assumptions

- **Workload:** one user, a FastAPI app with Jinja2/HTMX, PostgreSQL (the DB stays small, well under 5 GB, *estimate*), a scanner every hour or day (yfinance + pandas), and a few Gemini calls a day. Egress is tiny (single user). *Sizing estimate (not measured):* 2 GB RAM is the minimum for app + Postgres + pandas scanner, and 4 GB is comfortable.
- **Exchange rates:** NBP table A no. 196/A/NBP/2026 of **2026-10-08**. **1 EUR = 4.3789 PLN**, **1 USD = 3.9132 PLN** (so 1 USD ≈ 0.8936 EUR). Source: <https://api.nbp.pl/api/exchangerates/rates/a/eur/last/3/?format=json> and <https://api.nbp.pl/api/exchangerates/rates/a/usd/last/1/?format=json>.
- **VAT:** prices are shown **net (excl. VAT)** unless marked gross. Raul is a private consumer in Poland, so EU providers charge **23% Polish VAT** on top. "Gross" below = net × 1.23. Exceptions are prices already quoted gross: Mikrus, OVH PLN gross, netcup's 19% DE VAT label. US PaaS bill in USD, and the card's FX fee is not included.
- **Labels:** "*unverified*" means I couldn't confirm it on an official page. "*estimate*" means my calculation or assumption, not a quote.

## Comparison table

| Option | Monthly cost (net → gross 23%) | EU region | Postgres + backups | Scheduler / always-on | HTTPS | Encryption at rest | Ops effort (learner) | Lock-in | Main gotchas |
|---|---|---|---|---|---|---|---|---|---|
| **Hetzner CX23** + IPv4 + backups (+ Storage Box) | €7.09 → €8.72 (38 PLN); with BX11 €10.29 → €12.65 (55 PLN) | DE (FSN/NBG), FI (HEL) | Self-managed in Docker. Daily disk backups (7 slots, other DC) + own `pg_dump` to Storage Box | Yes, always on (cron/systemd/APScheduler) | Caddy + Let's Encrypt, or Tailscale | Not by default. Own LUKS / column encryption (*per third-party docs*) | Medium-high (Linux, Docker, updates) | Very low (plain Linux) | 2026 price rises. CX "cost-optimized" line showed "currently not available" on 2026-10-08 (use CAX11/CX33 if so) |
| **OVH VPS-1** (Warsaw) | 16.32 PLN net → 20.07 PLN gross (€4.58) "from" price | PL (Warsaw) + FR/DE etc. | Self-managed. Daily backup of last 24 h included. Premium 7-day backup from 4.70 PLN net | Yes | Caddy / Tailscale | Not stated (*unverified*) | Medium-high | Very low | "From" price; month-to-month may be higher (€4.49 per third party, *unverified*). Only a 24 h backup by default |
| **Contabo Cloud VPS 4** | €4.40 → €5.41 (24 PLN) on a 24-month term | DE / FR (Lauterbourg) | Self-managed. Auto Backup is a paid add-on (price *unverified*) | Yes | Caddy / Tailscale | Not stated (*unverified*) | Medium-high | Low | Price is for a 24-month term. Setup fee on the entry plan. Fair-use traffic |
| **netcup VPS 500 G12.5** | €7.03 incl. 19% DE VAT (≈€5.91 net → €7.27 with PL VAT) | AT/DE/NL | Self-managed. Snapshots | Yes | Caddy / Tailscale | Not stated | Medium-high | Low | Shown price needs a **24-month minimum contract** |
| **Mikrus 3.0 / 3.5** (PL company) | 130 / 197 PLN **gross per year** = 10.83 / 16.42 PLN a month | FI (Hetzner Helsinki DC) | Self-managed, or a shared PG (avoid for private data). Backup space offered (size *unverified*) | Yes | Via Cloudflare or Mikrus mechanisms; **no own IPv4** | LXC container, so no own disk encryption (*inference*) | Medium-high, Polish community | Low | 2 GB is tight; CPU throttled under sustained load; annual prepay only |
| **DigitalOcean** Basic 2 GB (+ Managed PG) | $12 (€10.72) → €13.19; + daily backups 30%; + Managed PG $15.15 → total ≈ €29.84 gross | FRA1, AMS3, LON1 | Managed PG has daily backups + 7-day PITR | Yes | Caddy / Tailscale / DO LB | Managed DB yes (*per DO*); Droplet disk *unverified* | Medium (Droplet) / lower with Managed PG | Low-medium | Expensive for the specs; US company |
| **Scaleway** DEV1-S (+ IPv4) | €6.55 + IPv4 €3.65 = €10.20 → €12.55 (+ block storage, *unverified*) | FR (Paris), NL, **PL (Warsaw)** | Managed PG DB-DEV-S ≈ €0.0156/h (~€11.4/mo) or self-managed | Yes | Caddy / Tailscale | *unverified* | Medium-high | Low | IPv4 billed separately; Stardust (€0.43 + IP) often scarce (*unverified*) |
| **Fly.io** (fra) | App 512 MB $3.69 (iad price; fra ~15% higher) + **Managed PG Basic $38** → ≈ €46 gross; unmanaged PG ≈ €8 gross | fra, ams, cdg, arn, lhr (MPG: fra, ams, lhr) | MPG: backups + HA included. Unmanaged Fly Postgres is "unsupported" | Yes (always-on Machine, or scheduled Machines) | Automatic | Volumes encrypted by default | Medium (CLI, Docker) | Medium (fly.toml, Machines) | **No free tier**, card required. Managed PG dominates the cost |
| **Render** (Frankfurt) | Web $7 + PG $6 + cron ≥$1 = $14 (€12.51) → €15.39 (67 PLN); with a $7 worker instead of cron ≈ €22 gross | Frankfurt | Managed. **PITR 3 days (Hobby)**, 7 days (Pro). Logical backups on paid. Free PG: no backups, expires after 30 d | Paid: cron jobs + background workers. **Free web sleeps after 15 min** | Automatic | AES-256 at rest | **Low** | Medium (render.yaml; Postgres is portable) | Free tier unusable for the scanner. 5 GB/month bandwidth on Hobby |
| **Railway** (Amsterdam) | Hobby $5 incl. $5 usage; realistic ≈ $5–10 (*estimate*) → €5.50–11 gross | EU West (Amsterdam) | Postgres template on a volume. Volume backups daily (kept 6 d) / weekly / monthly | Yes (always-on services + cron schedules) | Automatic | *unverified* | Low-medium | Medium | Usage-billed (RAM $10/GB-month). Hobby volumes max 5 GB. Backups "still under development" per docs |
| **Koyeb** (Frankfurt) | New users: **Pro $29/mo** (incl. $10 compute) → ≈ €32 gross | Frankfurt | Serverless PG: free 5 h active time/1 GB, Small $29.76/mo | Workers on paid; free instance sleeps after 1 h | Automatic | Yes (per pricing page) | Low | Medium | **Starter/free plan closed to new users** (Mistral acquisition, Feb 2026) |
| **Neon** (DB only) | Free $0; Launch ≈ $3–5/mo for this load (*estimate*) | Frankfurt, London (AWS) | Free: 6 h history; Launch: up to 7 days instant restore | n/a (DB only); scale-to-zero after 5 min | TLS | Yes (AWS-backed; *not re-verified*) | Low | Low (plain Postgres) | Free: **1 GB/project**, 100 CU-h/project, 5 GB egress; cold starts |
| **Supabase** (DB only) | Free $0; Pro $25 → ≈ €27.5 gross | Frankfurt, Paris, Ireland, Stockholm, Zurich… | Free: **no backups**; Pro: daily, 7 days; PITR $100/mo | n/a | TLS | Yes (*not re-verified*) | Low | Low-medium | **Free projects pause after 1 week of inactivity**; 500 MB |
| **Oracle Cloud Always Free** | €0 (card verification required) | Home region, chosen once (several EU regions) | Self-managed on the VM; 5 free volume backups; 20 GB object storage | Yes, but see reclamation | Caddy / Tailscale | Block volumes AES-256 by default | High (OCI console, networking, Arm) | Low-medium | **Idle VMs reclaimed**; "out of host capacity"; A1 is now **2 OCPU / 12 GB**; idle accounts may be terminated |
| **Home Raspberry Pi 5 / mini-PC** + Tailscale or Cloudflare Tunnel | Electricity ≈ 3.8–7.6 PLN/mo (*estimate*); tunnel/VPN $0 | Your home (PL) | Self-managed; off-site copy needed (e.g. Storage Box +14 PLN net) | Yes (always on) | Tailscale `*.ts.net` certs or Cloudflare edge | Full control (LUKS) | High (hardware + Linux + network) | None | Upfront hardware; home outages; residential uplink; theft/fire → backups must be off-site |

## Per-option notes

### 1. Small VPS

Every VPS option has the same architecture: one Linux VM running **Docker Compose** with `caddy` (TLS, HTTP→HTTPS, HSTS), `app` (uvicorn bound to the internal network only), `db` (postgres:16, no published port) and `scanner`. The scanner can be the same image running `python -m app.scanner` under a cron-like loop, or a **systemd timer** on the host calling `docker compose run --rm scanner`. Both satisfy #58 ("APScheduler in-process or a cron/systemd timer calling a CLI"). A VPS never sleeps, so an always-on scheduler is fine.

**Encryption at rest on a VPS:** none of the budget VPS providers advertises provider-side disk encryption. Choices:
- (a) **LUKS** on an attached volume holding the Postgres data. The catch is that it needs the passphrase after every reboot, which is awkward for a learner.
- (b) **Column-level encryption** for holdings (#57), e.g. Fernet, with the key from the secrets file.
- (c) Rely on **encrypted backups** (restic/age) plus provider physical security.

My suggestion is (b) + (c), and to decide in #56/#57.

#### Hetzner Cloud (DE/FI)
- **Price** (new orders since 15 June 2026, net): CX23 **€5.49**/mo, CAX11 (Arm) €5.99, CX33 €8.49. Primary IPv4 **€0.50**/mo. **Backups = 20% of the server price** (7 daily slots). Storage Box BX11 (1 TB) **€3.20**/mo (*third-party, Oct 2026*). Object Storage from **€6.49**/mo.
- **Specs:** CX23 is 2 vCPU / 4 GB / 40 GB NVMe / 20 TB traffic (*per third-party listings; Hetzner page is JS-rendered*).
- **Backups:** daily disk images stored "in the same location … usually in a different data center". They're deleted with the server, so they're not a real off-site backup. Add `pg_dump | age/restic` to a **Storage Box in HEL** when the server is in FSN/NBG.
- **Encryption:** volumes are not encrypted by Hetzner; use LUKS yourself (*per third-party docs + Hetzner CSI issue, not on an official Hetzner page*).
- **Availability:** on 2026-10-08 the hetzner.com/cloud page showed "Shared Resources – Currently not available" next to the cost-optimized line. If CX23 can't be ordered, CAX11 (Arm; Python/Postgres images are multi-arch) or CX33 are the fallbacks.
- **Learner fit:** large tutorial base (community.hetzner.com), hourly billing, no commitment, firewall in the console. *Opinion:* the simplest "real server" for learning.

#### OVH VPS 2027 range (Warsaw available)
- **Price:** VPS-1 (2 vCores / 4 GB / 40 GB NVMe, 500 Mbps, unlimited traffic) **from 16.32 PLN net / 20.07 PLN gross** a month on the official PL page. Third-party trackers give €3.81 (12-month) vs **€4.49 month-to-month** (*unverified on the official page*).
- **Backups:** a daily automatic backup of the last 24 h is included (stored 7 days and replicated in the same DC, per the footnote). Premium (restore up to 7 days back) is from 4.70 PLN net; snapshots from 1.30 PLN net.
- **Location:** an OVH datacenter in **Poland**. Pricing is in PLN, and OVH says the data is not subject to the US CLOUD Act.
- **Gotchas:** the "from" price depends on commitment and location. Third-party reviews mention payment-verification delays and hard-to-reach support (*anecdotal*).

#### Contabo
- **Price:** Cloud VPS 4 (4 vCPU / 8 GB / 100 GB SSD, 200 Mbit/s) is **€4.40 net (€5.50 incl. DE VAT)** "for the first 24 months" on the DE page. Setup fees apply only to the entry plan. Auto Backup is a paid add-on (price *unverified*).
- EU location: Lauterbourg (FR/DE border), no location fee.
- **Gotchas:** the headline price needs a 24-month term; outbound traffic is fair use. The specs are large for the money. Its reputation for performance and support is mixed (*anecdotal, third-party ratings*).

#### netcup
- VPS 500 G12.5 (2 vCore / 4 GB / 64 GB) costs **€7.03/mo incl. 19% DE VAT** on a **24-month minimum contract**, with the location "any EU (AT/DE/NL)". A specific location (Nuremberg/Vienna/Amsterdam) is +€1.04. A 1-month contract costs more (+€2.47 shown on the configurator). Polish VAT would apply instead of DE VAT.

#### Mikrus (mikr.us, Polish company)
- **Prices are gross per year, with no price rises since 2018 (per Mikrus):** 2.1 (1 GB/10 GB) 75 PLN, **3.0 (2 GB/25 GB) 130 PLN**, **3.5 (4 GB/40 GB) 197 PLN**, 4.1 (8 GB) 395 PLN. A 30-day trial of 2.1 costs 7 PLN.
- **Platform:** servers are in **Helsinki (Hetzner DC)**. Each VPS is an **LXC container** (shared kernel) with **no own public IPv4**: you get forwarded TCP/UDP ports plus your own IPv6, and custom domains go through Cloudflare or Mikrus tools. CPU is dynamically throttled under sustained load. Shared MySQL/PostgreSQL is available on 2.x/3.x. For private portfolio data, run your own Postgres instead.
- **Fit:** the cheapest real option (10.83 PLN/month for 3.0) with Polish support and invoices. But 2 GB is tight for Postgres + pandas (*estimate*), so 3.5 is safer. The lack of IPv4 makes HTTPS slightly fiddlier, and Tailscale or Cloudflare Tunnel solves it.

#### DigitalOcean
- Basic Droplets: 1 GB **$6**, 2 GB **$12**, 4 GB **$24**. Backups are 20% (weekly) or 30% (daily) of the Droplet price.
- Managed PostgreSQL from **$15.15**/mo (1 GB) with daily backups and PITR (7 days) (*per DO search snippet of the pricing/docs pages*).
- EU regions: Amsterdam, Frankfurt, London.
- Fit: the nicest managed-DB story among VPS clouds, but about 2× Hetzner/OVH for the same RAM.

#### Scaleway (French; has a Warsaw region)
- DEV1-S (2 vCPU / 2 GB) **€0.00898/h ≈ €6.55/mo**; STARDUST1-S (1 GB) €0.0006/h ≈ €0.43/mo. IPv4 is extra: **€0.005/h ≈ €3.65/mo**. Block storage is extra (*not priced here*). Managed PostgreSQL DB-DEV-S is €0.0156/h (≈€11.4/mo); backups/snapshots cost €0.03/GB-month.
- Paris, Amsterdam and **Warsaw** regions. Per-type stock in WAW is *unverified*.

### 2. PaaS + managed/free Postgres

**Key scanner point:** on any platform where the web service **sleeps**, an in-process APScheduler won't run while it's asleep. Use a **separate cron job or worker** (Render cron, Railway cron schedule, Fly scheduled Machine), or keep a paid always-on instance.

#### Fly.io
- **No free tier** since Oct 2024 for new orgs: a trial of 2 h runtime or 7 days, then a **card is required**.
- shared-cpu-1x 256 MB costs $2.19, 512 MB $3.69 and 1 GB $6.70 per 30 days (iad prices). Frankfurt is about 15% more: their example puts a 1 GB Machine at $7.73 in fra. Volumes are $0.15/GB; snapshots $0.08/GB beyond 10 GB free; egress $0.02/GB in EU.
- **Managed Postgres Basic $38/mo** (shared-2x, 1 GB) + $0.28/GB storage. All MPG plans include HA, backups and pooling. MPG regions in Europe: **fra, ams, lhr**.
- Unmanaged "Fly Postgres" (~$2/mo single node) is officially **unsupported**, so you own the backups.
- Volumes are encrypted at rest by default.
- **Verdict:** good tech, but either $45+/mo (managed DB) or self-managed DB on a PaaS (the worst of both).

#### Render
- **Hobby workspace $0** + compute: web "Starter" 0.5 CPU/512 MB **$7**; background worker the same price. **Postgres basic-256mb $6** and basic-1gb $19, with storage at $0.30/GB. **Cron jobs** are billed per minute ($0.00016/min for 512 MB) with a **minimum $1/month per cron job**.
- Postgres includes **PITR (3 days on Hobby, 7 on Pro)** and logical backups on paid plans. Data is encrypted at rest (AES-256). Region: **Frankfurt**. GDPR DPA on all tiers.
- **Free-tier gotchas (official docs):**
  - Free web services **spin down after 15 min** without inbound traffic, with ~1 min cold start.
  - Filesystem is ephemeral.
  - 750 free instance hours a month.
  - **Free Postgres expires 30 days after creation**: 14-day grace, then deleted. Free Postgres has **no backups** and is limited to 1 GB.
  - Hobby includes 5 GB bandwidth a month, then $0.15/GB.
- **Verdict:** the lowest-ops paid option with real backups. ~$14/mo (web + DB + cron). Recommended **fallback**.

#### Railway
- Hobby **$5/mo including $5 usage**. Usage: RAM $10/GB-month, CPU $20/vCPU-month, volumes $0.15/GB, egress $0.05/GB. *Estimate:* app 0.25 GB + Postgres 0.25 GB + light CPU ≈ $6/mo total.
- The Free plan ($1/mo credit, 0.5 GB per service) is too small.
- **EU West: Amsterdam.** Postgres is a template on a volume. **Volume backups:** daily (kept 6 days), weekly (27 d) or monthly (89 d), restorable only into the same project. Docs say the feature is "still under development" and that wiping a volume deletes all its backups, so keep your own `pg_dump` off-site too.
- Hobby volumes are capped at **5 GB**.
- **Verdict:** cheap and easy. Backups are less mature than Render's PITR.

#### Koyeb
- **Starter (free) plan is being removed for new users** after the Mistral AI acquisition (Koyeb blog, Feb 2026). New accounts need **Pro $29/mo** (includes $10 compute).
- Free instance (legacy accounts only): 0.1 vCPU/512 MB, **scales to zero after 1 h without traffic**, can't be a worker.
- Eco instances in Frankfurt from $1.61/mo. Serverless Postgres in Frankfurt: free 5 h active time/1 GB; Small $29.76/mo.
- A **$29 card pre-authorization** is placed at sign-up.
- **Verdict:** not cost-effective for one user in 2026.

#### Neon (Postgres only)
- **Free: 1 GB storage/project**, **100 CU-hours/project/month**, scale-to-zero after 5 min (can't be disabled), **6 h history** (restore window), 5 GB egress.
  - Running out of CU-hours or egress suspends compute until next month. Going over 1 GB blocks writes. No data is deleted.
- **Launch:** $0.106/CU-hour, $0.35/GB-month, up to 7-day restore, scale-to-zero can be disabled. *Estimate:* an hourly scanner wakes a 0.25 CU compute ~24×/day for ~10 min, about 30 CU-h/month. That fits Free, and costs ≈ $3/mo on Launch.
- Regions: **AWS Frankfurt** and London. Now "from Databricks".
- **Fit:** a sensible DB for the PaaS route (e.g. Render web + Neon), but adds a second vendor and cold-start latency.

#### Supabase (Postgres only)
- **Free:** 500 MB, **paused after 1 week of inactivity**, **no automatic backups**, 2 active projects.
- **Pro $25/mo** (includes Micro compute, 8 GB disk, daily backups kept 7 days). PITR costs **$100/mo** per 7 days.
- Many EU regions (Frankfurt, Paris, Ireland, Stockholm, Zurich). Note: the "Europe" general region can include non-EU London/Zurich, so pick a specific EU region.
- **Verdict:** overkill and pricey for this app. The free tier pause is risky, though a daily scanner would keep it active.

### 3. Oracle Cloud Always Free
- **Current official limits** (Oracle docs, Oct 2026):
  - Ampere A1: **1,500 OCPU-hours + 9,000 GB-hours a month, equivalent to 2 OCPUs / 12 GB** (less than the older 4/24 often quoted online).
  - 2× AMD E2.1.Micro (1 GB).
  - 200 GB block storage total, **5 volume backups**, 20 GB object storage, **10 TB/month egress**.
- Block volumes, boot volumes and backups are **AES-256 encrypted at rest by default**.
- **Gotchas:**
  - **Idle reclamation:** over 7 days, if CPU p95 < 20%, network < 20% and memory < 20% (A1), the instance is deemed idle and may be reclaimed. A single-user app usually is idle.
  - **"Out of host capacity"** errors in the home region.
  - Free resources only exist in the **home region, chosen once**.
  - A **credit/debit card is required** for verification (no prepaid/virtual cards).
  - **Accounts idle for 30+ days may be deemed abandoned and suspended or terminated.**
  - Trial-period A1 instances above free limits are disabled and deleted after 30 days.
  - No managed Postgres in Always Free (Autonomous DB is Oracle, not Postgres).
- **Verdict:** fine as a free experiment, **not** for the only copy of private portfolio data. If used, keep off-site backups and consider upgrading to Pay-As-You-Go, which avoids reclamation (*commonly reported, unverified*).

### 4. Home server (Raspberry Pi / mini-PC) behind Tailscale or Cloudflare Tunnel
- **Hardware:**
  - Raspberry Pi 5 **4 GB: $110** official US price after the 1 April 2026 memory-driven increase (8 GB +$50, per the Raspberry Pi announcement and CNX summary). That's ≈ 430 PLN net, before EU retail VAT and shipping (*the PL shop price is unverified*).
  - Add an NVMe/SSD (avoid SD-card wear for Postgres), official PSU and case: **≈ 200–400 PLN** (*estimate, unverified*).
  - So **≈ 650–900 PLN total** (*estimate*). A used mini-PC or an existing spare laptop is an alternative (*price not researched*).
- **Electricity** (*estimate*): the 2026 average G11 all-in rate is **≈1.04 PLN/kWh gross** (range 0.96–1.10; Interia/URE).
  - Pi 5 at ~5 W average (*assumed*): 3.65 kWh/mo, **≈3.8 PLN/mo**.
  - Mini-PC at ~10–15 W (*assumed*): **≈7.6–11.4 PLN/mo**.
- **Access:**
  - **Tailscale Personal** is free for non-commercial use (6 users, unlimited user devices). It gives private access plus HTTPS certificates for `*.ts.net`. This matches #56 option 2 ("private network + login") and exposes **no public port**, the safest for a learner.
  - **Cloudflare Tunnel** (`cloudflared`) is free and outbound-only. It needs a domain on Cloudflare (domain cost not researched). TLS terminates at Cloudflare, so Cloudflare can see the traffic. That's a privacy trade-off; add Cloudflare Access (Zero Trust free ≤ 50 users) in front of the app login.
- **Encryption at rest:** full control (LUKS on the SSD). Needed, because physical theft is the main risk.
- **Backups:** must leave the house, e.g. encrypted restic/`pg_dump` to a Hetzner Storage Box (+€3.20 net) or cloud object storage.
- **Gotchas:**
  - Home power or internet outages stop the scanner.
  - Router/ISP changes.
  - Arm64 image builds (fine for Python/Postgres).
  - Raul maintains the hardware.
- **Plus:** a residential IP may be treated more kindly by Yahoo's rate limiting than datacenter IPs (*plausible, unverified; worth testing from any cloud VM before committing*).

## Recommended setup

### Primary: Hetzner Cloud CX23 (or OVH VPS-1 Warsaw for the cheapest equivalent)

| Item | Net €/mo | Gross (23%) |
|---|---|---|
| CX23 (2 vCPU / 4 GB / 40 GB), FSN or NBG | 5.49 | |
| Primary IPv4 | 0.50 | |
| Hetzner Backups (20%) | 1.10 | |
| Storage Box BX11 in **HEL** (off-site, other country) | 3.20 | |
| **Total** | **€10.29 (45 PLN)** | **€12.65 ≈ 55 PLN** |
| Lean variant (no Storage Box; copy dumps to home PC instead) | €7.09 | €8.72 ≈ 38 PLN |
| OVH VPS-1 Warsaw + BX11 | €6.93 | €8.52 ≈ 37 PLN |

Plan for **≈ 40–60 PLN/month gross** plus Gemini API usage, which is not hosting. Optionally add a domain.

**How it would work:**
1. **Deploy:** Ubuntu LTS, SSH keys only, `ufw`/Hetzner firewall (22 + 443 only, or **only Tailscale** with no public ports), unattended-upgrades. Docker Compose services: `caddy`, `app`, `db`, `scanner`. Secrets go in `/etc/investment-ai/.env` (chmod 600), outside the repo and image.
2. **Exposure** (#56 Q2 / #48): the simplest secure start is **Tailscale-only + app login**, so no public attack surface. Public HTTPS via Caddy (auto Let's Encrypt, HSTS) comes later, once #48 (login, rate limit, optional TOTP) is done.
3. **Scheduler** (#58): a `scanner` container running the scanner CLI under a systemd timer (`OnCalendar=hourly` or weekdays after GPW/US close). That's simpler to debug than in-process APScheduler, survives app restarts and logs per run. Throttle and cache per R1.
4. **Backups** (#56 AC):
   - Nightly `pg_dump -Fc`, encrypted with **age** (or **restic** with a repo password), pushed over SFTP to the Storage Box sub-account. Retention: 7 daily / 4 weekly / 6 monthly.
   - Hetzner daily images as a second layer.
   - **Monthly test restore** into a scratch container, documented.
   - Keep the age private key/restic password **off the server** (password manager).
5. **Encryption at rest:** encrypted backups (above) + **column-level encryption for holdings** (#57) with a key from the secrets file. Optionally LUKS on a Hetzner Volume for `/var/lib/postgresql` if Raul accepts entering a passphrase after reboots.

### Fallback: Render (Frankfurt), managed

| Item | USD/mo | Gross EUR / PLN |
|---|---|---|
| Web service Starter (0.5 CPU / 512 MB) | 7 | |
| Postgres basic-256mb (1 GB incl., PITR 3 days) | 6 | |
| Cron job for the scanner (min $1) | ~1 | |
| **Total** | **≈ $14 (€12.51 net)** | **≈ €15.4 ≈ 67 PLN** |

- Scanner runs as a **Render Cron Job** (same repo, `python -m app.scanner`). HTTPS, TLS and encryption at rest are managed.
- **Add your own weekly encrypted `pg_dump`** to Storage Box/object storage (Render PITR only covers 3 days on Hobby).
- Upgrade the DB to basic-1gb ($19) if 256 MB RAM proves too small.

**Why not the others as primary/fallback:**
- Fly.io: $38 managed DB, or unsupported self-managed DB.
- Koyeb: $29 minimum for new users.
- Supabase Pro: $25, with PITR at $100.
- Railway: viable and cheaper than Render, but EU = Amsterdam only and backups are self-described as still in development. It's a fine second fallback.
- Oracle Free: reclamation and account-termination risk.
- Contabo/netcup: 24-month terms for the advertised price.
- Mikrus: great value and Polish, but no IPv4, an LXC container (no own disk encryption) and 2 GB on 3.0. Mikrus 3.5 (16.42 PLN/mo gross) is a credible budget alternative if Raul is comfortable with Tailscale or Cloudflare.

## Open decisions for Raul (feed #56)
1. Budget: is ~40–60 PLN/month OK (VPS), or ~70 PLN (Render) for less ops?
2. Exposure: **Tailscale-only** (recommended to start) vs public HTTPS + login.
3. Encryption at rest: column-level for holdings + encrypted backups (recommended) vs full LUKS.
4. Backup destination: Hetzner Storage Box (recommended) vs home PC vs object storage.
5. Before choosing a cloud VM, run a quick yfinance test from it (datacenter-IP rate limiting is a known community complaint; *unverified*).

## Sources (accessed 2026-10-08)
- Exchange rates: NBP table A 196/A/NBP/2026, <https://api.nbp.pl/api/exchangerates/rates/a/eur/last/3/?format=json>, <https://api.nbp.pl/api/exchangerates/rates/a/usd/last/1/?format=json>
- Hetzner price adjustment (15 June 2026, cloud prices): <https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/>
- Hetzner Primary IP pricing (€0.50 IPv4): <https://docs.hetzner.com/cloud/servers/primary-ips/overview/>
- Hetzner backups 20% / 7 slots: <https://docs.hetzner.com/cloud/billing/faq/>, <https://docs.hetzner.com/cloud/servers/backups-snapshots/faq/>
- Hetzner Object Storage €6.49: <https://www.hetzner.com/storage/object-storage/>
- Hetzner Storage Box BX11 €3.20 (third-party, Oct 2026): <https://vpssnaps.com/learn/storage/hetzner-storage-box-backups>, product page <https://www.hetzner.com/storage/storage-box/bx11/>
- Hetzner cloud page (availability note, GDPR, locations): <https://www.hetzner.com/cloud>
- CX23 specs (third-party): <https://www.vpsbenchmarks.com/hosters/hetzner/plans/cx23>
- Hetzner volume encryption (third-party): <https://syself.com/docs/hetzner/apalla/security/encrypt-data-disks>, <https://github.com/hetznercloud/csi-driver/issues/1101>
- OVH VPS (PL prices, backups): <https://www.ovhcloud.com/pl/vps/>; m2m vs 12-month (third-party): <https://dev.to/hostingsift/we-scraped-vps-prices-nightly-for-up-to-196-nights-273-plans-never-moved-and-our-first-query-520i>
- Contabo VPS (DE prices): <https://contabo.com/de/vps/>; EU location: <https://contabo.com/blog/contabo-eu-data-centers-latency-gdpr/>
- netcup VPS 500 G12.5: <https://www.netcup.com/en/server/vps/vps-500-g12-iv-12m>
- Mikrus pricing/FAQ: <https://mikr.us/>
- DigitalOcean Droplets: <https://www.digitalocean.com/pricing/droplets>; Managed DB: <https://www.digitalocean.com/pricing/managed-databases>, <https://docs.digitalocean.com/products/databases/postgresql/details/pricing/>
- Scaleway instances: <https://www.scaleway.com/en/pricing/virtual-instances/>; network/IPv4: <https://www.scaleway.com/en/pricing/network/>; managed DB: <https://www.scaleway.com/en/pricing/managed-databases/>
- Fly.io pricing: <https://fly.io/docs/about/pricing/>; regions: <https://fly.io/docs/reference/regions/>; MPG: <https://fly.io/docs/mpg/>; volumes encryption: <https://fly.io/docs/volumes/overview/>
- Render pricing: <https://render.com/pricing>; free limits: <https://render.com/docs/free>; cron min $1: <https://render.com/docs/cronjobs>; regions: <https://render.com/docs/regions>; Postgres encryption: <https://render.com/docs/postgresql-creating-connecting>
- Railway pricing: <https://railway.com/pricing>; backups: <https://docs.railway.com/reference/backups>; regions: <https://docs.railway.com/reference/deployment-regions>
- Koyeb pricing: <https://www.koyeb.com/pricing>; instances/free: <https://www.koyeb.com/docs/reference/instances>; pricing FAQ: <https://www.koyeb.com/docs/faqs/pricing>; Starter removal: <https://www.koyeb.com/blog/koyeb-is-joining-mistral-ai-to-build-the-future-of-ai-infrastructure>
- Neon pricing: <https://neon.com/pricing>; regions: <https://neon.com/docs/introduction/regions>
- Supabase pricing: <https://supabase.com/pricing>; regions: <https://supabase.com/docs/guides/platform/regions>
- Oracle Always Free: <https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm>; FAQ: <https://www.oracle.com/cloud/free/faq/>; encryption: <https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/blockvolumeencryption.htm>
- Tailscale pricing: <https://tailscale.com/pricing>; Cloudflare Tunnel: <https://developers.cloudflare.com/tunnel/>; Cloudflare plans: <https://www.cloudflare.com/plans/>
- Raspberry Pi price increases (1 Apr 2026): <https://www.raspberrypi.com/news/a-new-3gb-raspberry-pi-4-for-83-75-and-more-memory-driven-price-increases/>, <https://www.cnx-software.com/2026/04/01/raspberry-pi-4-3gb-launched-for-83-75-further-price-increases-announced-across-the-board-for-4gb-ram-hardware/>
- PL electricity 2026 (G11 ≈1.04 PLN/kWh): <https://biznes.interia.pl/gospodarka/news-ile-kosztuje-1-kwh-w-2026-roku-ceny-pradu-w-tauronie-pge-i-u,nId,23478259>
