# PiVAX Hacker Replicant

An AI tutor/copilot that sits next to a PiVAX replica: a web page with the
real VAX terminal session on the left, and a chat panel on the right that
knows VAX/VMS 7.3, DCL, and the "Cuckoo's Egg" history behind this
persona — and, if you let it, can type into the console itself.

Unlike this project's PiDP-11 sibling, this repo does **not** bundle a web
console app. It assumes you already have your own way to view/drive the
VAX terminal session in a browser (a ttyd/xterm.js bridge, a VNC-to-web
gateway, or whatever your PiVAX build already uses) — point `CONSOLE_URL`
at it and the left panel just embeds it. What this repo *does* provide:
the chat backend (right panel), the system prompt/persona, and the small
boot-API bridge that lets the chat agent read/type into the same terminal
session your console already shows.

It's part of a small family of "Hacker Replicant" AI tutors built for
different PDP/VAX/HP simulator replicas; this one is PiVAX-specific, but
the pattern (bring-your-own console + a tiny `screen`-reading boot-API + a
chat panel + an LLM backend) is reusable for other machines too.

## The "Cuckoo's Egg" persona

The chat persona is framed around Cliff Stoll's book *The Cuckoo's Egg*
(Doubleday, 1989) — the true story of how a 75-cent accounting discrepancy
at Lawrence Berkeley Laboratory in August 1986 led Stoll to uncover a
hacker (later identified as Markus Hess) who had broken into dozens of
military bases, universities, and research labs by exploiting **unchanged
factory-default passwords** on privileged VAX/VMS accounts — `FIELD` /
`SERVICE` (the standard field-service account) and `SYSTEM` / `MANAGER`.
See `skills/vms-cuckoos-egg.md` for the full system prompt, which uses this
story as the natural hook for explaining real VMS security concepts
(AUTHORIZE/SYSUAF, SET AUDIT, privilege masks, etc.) — it's deliberately
kept in Dutch, matching how the rest of this Hacker Replicant family
handles persona/knowledge files. These default-password examples are
public, 40-year-old historical security-awareness information, not a
live secret — treat them that way.

## How it works

```
Browser
 │
 ├─ Left panel:  <iframe> → your own existing web console (CONSOLE_URL)
 │      Bring your own -- this repo doesn't include one. Anything that
 │      shows the VAX terminal session in a browser works.
 │
 └─ Right panel: chat → POST /api/chat (SSE stream)
      │  this Node service (server.js)
      │
      ├─ LLM backend: any OpenAI-compatible /chat/completions API
      │  (local Ollama by default, or a hosted provider -- see below)
      │
      └─ when the control toggle is ON, two tools only:
           send_keys   → POST  <BOOTAPI_BASE>/keys    {"text": "..."}
           read_screen → GET   <BOOTAPI_BASE>/screen
           (served by pivax-bootapi.py, included in this repo)
```

There's no SIMH API involved anywhere. The machine's terminal runs inside
a GNU `screen` session; both your own web console and the chat agent's
tools talk to that *same* session, just via different mechanisms. The
agent's tools (`pivax-bootapi.py`) use two simple, stateless `screen`
primitives:

- `screen -X stuff <text>` — types text into the session, as if someone
  sat down and typed it.
- `screen -X hardcopy <file>` — writes a plain-text snapshot of the
  current screen contents to a file, which the API reads back.

That's the entire "control" surface for the agent: no shell access, no
filesystem access, nothing beyond what's visible in the same terminal your
console already shows.

### A note on `pivax-bootapi.py` and the HP3000

`pivax-bootapi.py` namespaces its URL paths by machine name (`/api/vax/screen`,
`/api/vax/keys`, driven by a `SESSIONS` dict), even though this repo only
ever uses the `vax` entry. That's because the script this was adapted from
was originally written to serve **two** co-located simulators from one
process — the internal deployment it came from also happened to run an
unrelated HP3000 simulator on the same physical host, so the script kept a
machine-namespace in the path instead of a flat `/api/screen` + `/api/keys`.

For a single-machine PiVAX setup, you only need the `"vax"` entry in
`SESSIONS` — the version in this repo already has it trimmed down to just
that. If you ever add a second simulator next to your PiVAX later, this
script is a ready-made template: add another `{"name": "session-name"}`
entry and you get `/api/<name>/screen` + `/api/<name>/keys` for free.

## LLM-agnostic by design

The chat backend talks to **any backend that speaks the OpenAI-compatible
`/chat/completions` API with tool/function calling** — that's one code
path for both:

- **Local** (default, free): point it at a local [Ollama](https://ollama.com)
  install. Ollama has spoken this API since mid-2024, nothing extra to
  configure beyond pulling a model that supports tool calling (`qwen3`,
  `llama3.1`+, `mistral-nemo`, etc. all do).
- **Cloud** (optional, for a faster/smarter option): point it at OpenAI,
  Groq, Together, Fireworks, DeepSeek, Mistral, OpenRouter, a hosted
  vLLM/TGI endpoint — anything OpenAI-compatible. See `.env.example` for
  examples.

No vendor SDK, no hard dependency on any single provider, no API key
required at all if you only use the local backend.

**A heads-up on local "thinking" models:** Ollama's OpenAI-compatible
endpoint (what the local backend uses) doesn't currently expose a way to
turn off a reasoning model's internal "thinking" step the way Ollama's own
native API does (`think: false`) — for `qwen3` specifically this means
every reply carries a few hundred tokens of hidden reasoning, adding
roughly 10-20 extra seconds per turn. `LLM_TIMEOUT_MS` already accounts for
this (default 180s), so nothing breaks, it just feels slower than it has
to. If snappier replies matter more to you than using a reasoning model
locally, point `LOCAL_MODEL` at a non-thinking model instead (`llama3.1`,
`mistral-nemo`, etc. all support tool calling without this overhead).

## Setup

### Setting up the base machine (if you don't have one yet)

This repo is the AI tutor layer only — it assumes a VAX/VMS simulator is
already running somewhere with its terminal attached to a `screen`
session. If you don't have that yet:

- **Simulator:** [open-simh](https://github.com/simh/simh) includes a
  VAX 8600 simulator (what the original build used), run under GNU
  `screen` so the session can be shared between your own web console and
  this repo's boot-API.
- **OpenVMS media and license:** this is the part we can't hand you a
  shortcut for. VAX/VMS licenses (including DEC/HPE TCPIP Services and
  DECnet) stopped being legally obtainable once the VSI hobbyist program
  was discontinued (2020/2025) — there is currently no known legitimate
  free route to OpenVMS installation media for a new hobbyist setup.
  Sourcing a valid license and media is on you; we're not linking or
  including any here.
- **Build-mechanics reference:** once you have legitimate media, the
  original PiVAX build followed the SIMH VAX8600 + OpenVMS 7.3 install
  walkthrough at [blog.poggs.com](https://blog.poggs.com) for the actual
  simulator configuration and boot process — useful for the *mechanics*
  of the install (disk setup, boot flow, console attach), independent of
  where your media comes from.
- **Networking (optional but recommended):** for CMU TCP/IP (the
  networking stack used in the original build, needed if you want the
  VMS guest reachable as its own host on your LAN rather than purely
  console-only) the install kit is `CMUIP066.iso` (savesets + FAQs,
  findable via general VMS-hobbyist archives) — set up as a CD-ROM device
  during the VMS install. A `tap`-interface-in-bridge setup on the host
  (rather than attaching the NIC directly to a physical interface) avoids
  a common hairpin-routing gotcha where the host can't reach the guest's
  own IP.

None of this is required to get the *chat tutor* running — `CONSOLE_URL`
and `BOOTAPI_BASE` just need to point at whatever VAX/VMS `screen` session
you end up with, however you got there.

### Prerequisites

- GNU `screen`, installed on the Pi (`apt install screen` on
  Debian/Raspberry Pi OS if it isn't already). `pivax-bootapi.py` shells
  out to it directly, and your own web console almost certainly does too.
- A running PiVAX (VAX 8600 / OpenVMS 7.3 under simh) with its terminal
  session attached to a `screen` session, and your own existing web
  console pointed at that same session. See "Setting up the base machine"
  above if you're starting from scratch.
- Node.js 18+ and Python 3 on that same host (or reachable over the
  network from it).
- [Ollama](https://ollama.com) running somewhere reachable (for the free
  local backend), or an API key for a cloud provider.

The chat backend and boot-API are plain Node/Python processes — they can
run on the PiVAX's own Pi, or the chat backend can run elsewhere and just
point `CONSOLE_URL`/`BOOTAPI_BASE` at the Pi over the network. The
boot-API needs to run on the Pi itself (it shells out to `screen`
directly).

### Install

```bash
git clone <this-repo-url>
cd pivax-hacker-replicant
npm install
cp .env.example .env
# edit .env: at minimum set CONSOLE_URL and BOOTAPI_BASE to match your setup
```

### Run the boot-API (on the Pi, bridges the chat agent to the console)

```bash
python3 pivax-bootapi.py
```

Edit the `SESSIONS` dict at the top of `pivax-bootapi.py` if your `screen`
session isn't named `vax`.

### Run the chat backend (right panel)

```bash
npm start
```

Open `http://<host>:8096/` (or whatever `PORT` you set) — `CONSOLE_URL`
should point at your own existing web console for the VAX terminal.

### Running both as services

See `docs/pivax-bootapi.service.example` and
`docs/pivax-hacker-replicant.service.example` for ready-to-adapt systemd
units.

## Configuration reference

All configuration is environment variables — see `.env.example` for the
full list with examples. The short version:

| Variable | What |
|---|---|
| `PORT` | Port the chat backend listens on |
| `CONSOLE_URL` | Your own existing web console, shown in the left panel |
| `BOOTAPI_BASE` | Where `pivax-bootapi.py` is reachable (default namespace: `/api/vax`) |
| `ACTION_LIMIT` | Tool calls per turn before the agent must ask to continue |
| `LOCAL_BASE_URL` / `LOCAL_API_KEY` / `LOCAL_MODEL` | Local (default) backend |
| `CLOUD_BASE_URL` / `CLOUD_API_KEY` / `CLOUD_MODEL` | Optional cloud backend |

## Safety model

- The control toggle is **off** on every page load — by default the agent
  only talks, it never touches the machine.
- When on, the agent gets exactly two tools (`send_keys`, `read_screen`),
  nothing else — no shell, no filesystem, no network access beyond the
  boot-API.
- After `ACTION_LIMIT` tool calls in one turn, the agent is cut off from
  further tool calls and must ask in plain text whether it may continue —
  no silent, unbounded action streak. A hard iteration cap (20) sits
  underneath as a defensive backstop against a broken loop.
- Everything the agent types is visible live in the same terminal session
  your own web console shows — no black box.
- This does **not** protect you from the agent typing something wrong (it's
  an LLM, it can make mistakes) — the boundary is on *what* it can touch,
  not on *how well* it types. Use a local/free backend if you want to
  experiment without any cost risk.

## Repository layout

```
server.js                      Chat backend (Node/Express, SSE, LLM-agnostic)
public/                        Chat panel UI (right side)
pivax-bootapi.py               screen -X stuff/hardcopy bridge for the chat agent's tools
skills/vms-cuckoos-egg.md      System prompt: VAX/VMS knowledge + Cuckoo's Egg persona + behavior rules
docs/                          Example systemd units (not installed automatically)
```

## Adapting this for a different replica

`pivax-bootapi.py` is deliberately small and machine-specific only in its
`SESSIONS` dict — it's a reasonable starting point for wiring up the same
pattern on a different PDP/VAX/HP/whatever replica: same two primitives
(`screen -X stuff` / `screen -X hardcopy`), same tiny HTTP wrapper.
`skills/vms-cuckoos-egg.md` is the only file that's actually VAX/VMS-specific
content; swap it for a system prompt about your own machine and point
`server.js` at the new file.

Since this repo doesn't bundle a web console (unlike the PiDP-11 Hacker
Replicant in this same family), adapting the *left panel* is just a matter
of pointing `CONSOLE_URL` at whatever console you already use — the chat
panel and the boot-API don't care what's actually driving it.

## Credits

Built by Rolf Peters with Seb (his homelab AI assistant). The PiVAX
hardware/software build itself draws on the broader open VAX/simh replica
and simulator community rather than a single named kit designer — if your
own PiVAX build follows a specific published guide, credit it there; this
repo only covers the AI tutor layer on top.

## License

MIT — see `LICENSE`.
