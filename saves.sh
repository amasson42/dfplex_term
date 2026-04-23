#!/bin/bash
# dfplex save manager — export and import fortress saves
# Usage:
#   ./saves.sh export            → saves_YYYY-MM-DD.tar.gz
#   ./saves.sh import FILE.tar.gz
#   ./saves.sh list              → list saves inside a backup

CONTAINER="df_multiplayer"
SAVE_PATH="/home/dfplayer/df/data/save"

case "$1" in

  export)
    DATE=$(date +%Y-%m-%d_%H-%M)
    FILE="saves_${DATE}.tar.gz"
    echo "Exporting saves to $FILE ..."
    docker exec "$CONTAINER" tar czf - -C "$SAVE_PATH" . > "$FILE"
    echo "Done: $FILE ($(du -sh "$FILE" | cut -f1))"
    ;;

  import)
    FILE="$2"
    if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
        echo "Usage: $0 import FILE.tar.gz"
        exit 1
    fi
    echo "Importing saves from $FILE ..."
    echo "WARNING: This will overwrite saves in the running container."
    read -p "Continue? [y/N] " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Aborted."
        exit 0
    fi
    docker exec "$CONTAINER" mkdir -p "$SAVE_PATH"
    cat "$FILE" | docker exec -i "$CONTAINER" tar xzf - -C "$SAVE_PATH"
    echo "Done. Restart DF to load the imported saves."
    ;;

  list)
    FILE="$2"
    if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
        echo "Usage: $0 list FILE.tar.gz"
        exit 1
    fi
    echo "Saves in $FILE:"
    tar tzf "$FILE" | grep -E "^(region[0-9]+|current)/?$" | sort
    ;;

  *)
    echo "dfplex save manager"
    echo ""
    echo "Usage:"
    echo "  $0 export              Export saves to saves_DATE.tar.gz"
    echo "  $0 import FILE.tar.gz  Import saves into running container"
    echo "  $0 list   FILE.tar.gz  List saves inside a backup"
    ;;

esac
