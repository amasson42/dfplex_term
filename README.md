# dfplex-term

Multiplayer Dwarf Fortress in your terminal, via SSH.

Each player gets their own independent view and cursor thanks to DFPlex.
No browser needed — pure terminal.

---

## Quick Start

### 1. Build and start

```bash
docker-compose up -d --build
```

The Dockerfile automatically downloads:
- Dwarf Fortress Classic 0.47.04
- DFHack 0.47.04-r1
- DFPlex v0.2.1

**First build takes ~5 minutes** (downloading ~200MB).

### 2. First time setup (once)

```bash
ssh dfplayer@YOUR_IP -p 2222
# password: dwarves

screen -r dwarf          # attach to DF (escape key is Ctrl-X, not Ctrl-A)
# → navigate title screen, embark or load a world
# → once in fortress, press Ctrl-S to save
Ctrl-X then D            # detach (DF keeps running)
```

### 3. Play

```bash
# Install client dependency once
pip install websocket-client

# Connect from any machine
python3 dfplex_client.py YOUR_IP 1234 YourNick
```

Friend connects:
```bash
python3 dfplex_client.py YOUR_IP 1234 FriendNick
```

After the first save, DF auto-loads the fortress on container restart.

---

## Client controls

| Key | Action |
|-----|--------|
| Arrow keys | Move cursor / scroll map |
| Space | Pause / unpause |
| All standard DF keys | Work normally |
| `\` | Toggle multiplexing (separate views per player) |
| `Ctrl-T` | Request your turn token |
| `Ctrl-Q` | Disconnect from dfplex (DF keeps running) |

---

## Useful commands

### Container management

```bash
# Start the server
docker-compose up -d

# Stop the server
docker-compose down

# Rebuild from scratch (after updating files)
docker-compose down && docker-compose up -d --build

# View container logs
docker logs df_multiplayer

# Open a shell inside the container
docker exec -it df_multiplayer bash
```

### Manually launching DF inside the container

If DF isn't running (e.g. after a crash), SSH in and run:

```bash
ssh dfplayer@YOUR_IP -p 2222

# Launch DF with DFHack in a persistent screen session
TERM=xterm-256color \
LD_LIBRARY_PATH=.:libs:./hack/libs:./hack \
LD_PRELOAD=./hack/libdfhack.so \
./libs/Dwarf_Fortress
```

Or wrap it in screen so it survives disconnects:

```bash
screen -dmS dwarf bash -c '
    cd ~/df
    TERM=xterm-256color \
    LD_LIBRARY_PATH=.:libs:./hack/libs:./hack \
    LD_PRELOAD=./hack/libdfhack.so \
    ./libs/Dwarf_Fortress 2>&1 | tee ~/df.log
'
screen -r dwarf   # attach (Ctrl-X D to detach)
```

### Checking DF status

```bash
# Is DF running?
pgrep -a Dwarf_Fortress

# Is DFPlex listening?
cat ~/df/dfplex_server.log

# Check for errors
cat ~/df/stderr.log | tail -20
cat ~/df/df.log | tail -20

# Is dfplex plugin loaded?
~/df/hack/dfhack-run plug dfplex

# Manually load a save
~/df/hack/dfhack-run load-save region1
```

### Fixing missing libs (after rebuild)

If DF fails with missing library errors:

```bash
# Run from outside the container
docker exec -it df_multiplayer bash -c "
    sudo cp ~/df/hack/libdfhack.so /usr/local/lib/
    sudo cp ~/df/hack/libdfhack-client.so /usr/local/lib/
    sudo cp ~/df/hack/liblua.so /usr/local/lib/
    sudo cp ~/df/hack/libprotobuf-lite.so /usr/local/lib/
    sudo ldconfig
    ln -sf /lib/x86_64-linux-gnu/libncursesw.so.6 /usr/lib/x86_64-linux-gnu/libncursesw.so.5
    ln -sf /lib/x86_64-linux-gnu/libncurses.so.6 /usr/lib/x86_64-linux-gnu/libncurses.so.5
    sudo ldconfig
"
```

### Save management

```bash
# Export saves to a file
./saves.sh export
# → saves_2026-04-23_14-30.tar.gz

# Import saves into running container
./saves.sh import saves_2026-04-23_14-30.tar.gz

# List saves inside a backup
./saves.sh list saves_2026-04-23_14-30.tar.gz
```

---

## Ports

| Port | Purpose |
|------|---------|
| 2222 | SSH (setup and administration) |
| 1234 | DFPlex WebSocket (dfplex_client.py) |
| 8000 | DFPlex HTTP (browser fallback) |

---

## Troubleshooting

**`Error opening terminal: alacritty` or similar**
Your terminal type isn't known inside the container. Fix:
```bash
export TERM=xterm-256color
```
Add to `~/.bashrc` to make it permanent.

**Screen steals my keys**
The escape key is `Ctrl-X` (not `Ctrl-A`). Detach with `Ctrl-X D`.

**dfplex shows blank screen**
DF is probably at the title screen. Attach with `screen -r dwarf`, load your fortress, save with `Ctrl-S`, then detach.

**`Disconnected (code=None)` in dfplex client**
DFPlex plugin isn't running. Check `cat ~/df/stderr.log | grep dfplex`.

**Keys not working in dfplex**
Make sure you're in fortress mode (not the title screen). Press `\` to toggle multiplexing, then try your keys.

**Save not persisting across container restarts**
Make sure you save with `Ctrl-S` before stopping. The Docker volume `df_saves` stores saves — don't use `docker-compose down -v` or you'll lose them.
