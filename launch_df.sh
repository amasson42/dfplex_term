#!/bin/bash
# Launches DFHack bypassing the setarch syscall that Docker blocks.
# This patches the dfhack script on-the-fly to skip setarch entirely.

cd ~/df

# Patch dfhack_setarch.txt to suppress the warning
echo "" > hack/dfhack_setarch.txt

# Run dwarfort directly with the same env dfhack would set up,
# but without the setarch wrapper that requires CAP_SYS_PERSONALITY
export LD_LIBRARY_PATH=".:$LD_LIBRARY_PATH"

# Check what the actual DF binary is called
if [ -f "./dwarfort" ]; then
    DF_BIN="./dwarfort"
elif [ -f "./df" ]; then
    DF_BIN="./df"
else
    echo "ERROR: Can't find DF binary. Contents of ~/df:"
    ls ~/df/
    exit 1
fi

echo "Launching $DF_BIN ..."
exec env LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
     LD_PRELOAD="./hack/libdfhooks_dfhack.so" \
     $DF_BIN "$@"
