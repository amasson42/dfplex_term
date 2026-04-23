#!/bin/bash
set -e

# Start SSH
service ssh start

# Start DF as dfplayer in a named screen session
su - dfplayer -c "
    screen -dmS dwarf bash -c 'cd ~/df && LD_LIBRARY_PATH=.:libs ./libs/Dwarf_Fortress 2>&1 | tee ~/df.log'
    echo 'Dwarf Fortress started in screen session \"dwarf\"'
"

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  DFPlex Server Running                            ║"
echo "║  SSH  → port 22    password: dwarves              ║"
echo "║  WS   → port 1234  (dfplex terminal client)       ║"
echo "║  HTTP → port 8000  (browser fallback)             ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# Keep container alive
tail -f /dev/null
