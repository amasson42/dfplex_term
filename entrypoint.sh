#!/bin/bash
set -e

service ssh start

# Serve dfplex_client.py for easy download
python3 -m http.server 8001 --directory /usr/local/share/dfplex &

su - dfplayer -c '
    screen -dmS dwarf bash -c "
        cd ~/df
        TERM=xterm-256color \
        LD_LIBRARY_PATH=.:libs:./hack/libs:./hack \
        LD_PRELOAD=./hack/libdfhack.so \
        ./libs/Dwarf_Fortress 2>&1 | tee ~/df.log
    "
    echo "DF started in screen session dwarf"

    # Auto-load most recent save once DFHack is ready
    (
        SAVE=$(ls -td ~/df/data/save/region* 2>/dev/null | head -1 | xargs basename 2>/dev/null)
        if [ -z "$SAVE" ]; then
            echo "No save found, skipping auto-load"
            exit 0
        fi
        echo "Will auto-load save: $SAVE"
        sleep 15
        for i in $(seq 1 90); do
            result=$(~/df/hack/dfhack-run load-save "$SAVE" 2>&1)
            case "$result" in
                *"title"*|*"Can"*|*"Could"*|*"not found"*|*"screen"*|*"connect"*)
                    sleep 2 ;;
                *)
                    echo "Auto-load result: $result"
                    break ;;
            esac
        done
    ) &
'

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  DFPlex Multiplayer Server started                       ║"
echo "║  SSH  → port 2222   password: dwarves                    ║"
echo "║  WS   → port 1234   dfplex_client.py YOUR_IP 1234 Nick   ║"
echo "║  DL   → curl YOUR_IP:8001/dfplex_client.py | python3 -   ║"
echo "╚══════════════════════════════════════════════════════════╝"

tail -f /dev/null
