# dfplex-term

A **real terminal client** for [DFPlex](https://github.com/white-rabbit-dfplex/dfplex) multiplayer Dwarf Fortress.

Each player SSH-es in and gets their **own independent view, cursor, and menus** — exactly as DFPlex was designed. No shared tmux session, no fighting over one screen.

---

## How it works

DFPlex runs inside a Docker container. It serves a WebSocket on port 1234
with per-player screen buffers (CP437 chars + 16-colour DF palette, delta-encoded).
`dfplex_client.py` connects over that WebSocket, decodes the frames, and renders them
as ANSI colour in your terminal using Python's `curses`. Keypresses are translated
back to JS key codes and sent to the server, which injects them into DF via DFHack.

---

## Setup

### 1. Assemble the DF bundle  (one-time, ~5 minutes)

DFPlex targets **Dwarf Fortress Classic 0.47.05** + **DFHack 0.47.05-r7**.

```bash
mkdir df_bundle && cd df_bundle

# 1. Dwarf Fortress Classic (free, Linux)
wget http://www.bay12games.com/dwarves/df_47_05_linux.tar.bz2
tar xjf df_47_05_linux.tar.bz2
mv df_linux/* .
rmdir df_linux

# 2. DFHack — extract ON TOP of DF folder
wget https://github.com/DFHack/dfhack/releases/download/0.47.05-r7/dfhack-0.47.05-r7-Linux-64bit-gcc-7.tar.bz2
tar xjf dfhack-0.47.05-r7-Linux-64bit-gcc-7.tar.bz2

# 3. DFPlex — extract ON TOP of DF+DFHack
wget https://github.com/white-rabbit-dfplex/dfplex/releases/download/v0.2.1-dfplex/dfplex-v0.2.1.zip
unzip dfplex-v0.2.1.zip

cd ..
```

Your directory should now look like:
```
dfplex-term/
  df_bundle/          ← DF + DFHack + DFPlex merged
    dfhack             (executable)
    libs/
    hack/
    data/
    ...
  dfplex_client.py
  Dockerfile
  docker-compose.yml
  entrypoint.sh
  motd
  README.md
```

### 2. Build and start the server

```bash
docker-compose up -d --build
```

DF + DFHack starts automatically inside the container. It may take 10–20 seconds
to reach the title screen on first launch.

### 3. Connect (you and your friend)

**Option A: SSH into the container, then run the client locally**

```bash
# On your machine (host):
ssh dfplayer@localhost -p 2222
# password: dwarves

# Once inside, just run:
dfplex

# Your friend (replace with your public IP):
ssh dfplayer@YOUR_IP -p 2222
# then: dfplex
```

**Option B: Run the client directly on your local machine (no SSH)**

If port 1234 is reachable:

```bash
pip install websocket-client
python3 dfplex_client.py YOUR_SERVER_IP 1234 YourNick
```

---

## Controls

| Key | Action |
|-----|--------|
| Arrow keys | Move cursor / navigate |
| All standard DF keys | Work as normal |
| `Ctrl-T` | Request your turn token (become active player) |
| `Ctrl-Q` | Disconnect (DF keeps running, fortress is safe) |
| `F1`–`F12` | Function keys |
| `Esc` | Cancel / back |

---

## Changing the password

```bash
docker exec -it df_multiplayer passwd dfplayer
```

Or add SSH key auth — edit `/etc/ssh/sshd_config` in the container and add
your public key to `/home/dfplayer/.ssh/authorized_keys`.

---

## Port reference

| Port | Purpose |
|------|---------|
| `2222` | SSH (players connect here) |
| `1234` | DFPlex WebSocket (terminal client) |
| `8000` | DFPlex HTTP (browser fallback — still works!) |

---

## Saves

Fort saves are stored in a named Docker volume (`df_saves`) and persist
across container restarts. To back up:

```bash
docker run --rm -v df_saves:/saves -v $(pwd):/out ubuntu \
    tar czf /out/saves_backup.tar.gz /saves
```

---

## Troubleshooting

**Screen looks garbled / wrong characters:**
Your terminal must support UTF-8. Run: `echo $LANG` — should show `UTF-8`.
Also ensure your terminal font includes CP437 characters (e.g. DejaVu Sans Mono,
Cascadia Code, or any "Nerd Font").

**Colours look wrong:**
Run `echo $TERM` — should be `xterm-256color`. Export it if not:
`export TERM=xterm-256color`.

**DF hasn't started yet:**
Check logs: `docker exec df_multiplayer cat /home/dfplayer/df_stdout.log`

**DFPlex plugin not found:**
Make sure `hack/plugins/dfplex.so` exists in your `df_bundle`. It should be
included in the DFPlex zip release.
