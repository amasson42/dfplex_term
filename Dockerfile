FROM debian:bullseye-slim
ENV DEBIAN_FRONTEND=noninteractive

# ── Runtime deps ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    screen \
    sudo \
    python3 python3-pip \
    # DF runtime libs
    libsdl1.2debian \
    libsdl-image1.2 \
    libsdl-ttf2.0-0 \
    libgtk2.0-0 \
    libglu1-mesa \
    libopenal1 \
    libsndfile1 \
    libncurses6 \
    libncursesw6 \
    libstdc++6 \
    # Download tools
    wget \
    unzip \
    bzip2 \
    bsdutils \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir websocket-client

# ── SSH setup ─────────────────────────────────────────────────────────────
RUN mkdir /var/run/sshd && \
    useradd -ms /bin/bash dfplayer && \
    echo 'dfplayer:dwarves' | chpasswd && \
    echo 'dfplayer ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    echo "PrintLastLog no" >> /etc/ssh/sshd_config && \
    echo "PrintMotd yes" >> /etc/ssh/sshd_config

# ── Download & assemble DF + DFHack + DFPlex ─────────────────────────────
# Versions pinned for DFPlex v0.2.1 compatibility
ENV DF_VERSION=47_04 \
    DFHACK_VERSION=0.47.04-r1 \
    DFPLEX_VERSION=v0.2.1-dfplex

RUN mkdir -p /home/dfplayer/df && cd /home/dfplayer/df && \
    # 1. Dwarf Fortress Classic
    wget -q "http://www.bay12games.com/dwarves/df_${DF_VERSION}_linux.tar.bz2" && \
    tar xjf df_${DF_VERSION}_linux.tar.bz2 --strip-components=1 && \
    rm df_${DF_VERSION}_linux.tar.bz2 && \
    # 2. DFHack
    wget -q "https://github.com/DFHack/dfhack/releases/download/${DFHACK_VERSION}/dfhack-${DFHACK_VERSION}-Linux-64bit-gcc-7.tar.bz2" && \
    tar xjf dfhack-${DFHACK_VERSION}-Linux-64bit-gcc-7.tar.bz2 && \
    rm dfhack-${DFHACK_VERSION}-Linux-64bit-gcc-7.tar.bz2 && \
    # 3. DFPlex — unzip into subdir then merge into df root
    wget -q "https://github.com/white-rabbit-dfplex/dfplex/releases/download/${DFPLEX_VERSION}/dfplex-v0.2.1-Linux64.zip" && \
    unzip -q dfplex-v0.2.1-Linux64.zip && \
    cp -r dfplex-v0.2.1-Linux64/. . && \
    rm -rf dfplex-v0.2.1-Linux64 dfplex-v0.2.1-Linux64.zip

# ── ncurses symlinks DF needs at runtime ─────────────────────────────────
RUN find /lib /usr/lib -name 'libncurses*.so*' -o -name 'libncursesw*.so*' 2>/dev/null | head -5
RUN ln -sf $(find /lib /usr/lib -name 'libncursesw.so.*' | head -1) /usr/lib/x86_64-linux-gnu/libncursesw.so.5 2>/dev/null || true &&     ln -sf $(find /lib /usr/lib -name 'libncurses.so.*' | head -1) /usr/lib/x86_64-linux-gnu/libncurses.so.5 2>/dev/null || true &&     ldconfig

# ── Configure DF ──────────────────────────────────────────────────────────
RUN cd /home/dfplayer/df && \
    # Force text/curses mode (no display in container)
    sed -i 's/\[PRINT_MODE:2D\]/[PRINT_MODE:TEXT]/' data/init/init.txt && \
    # Autosave every season
    sed -i 's/\[AUTOSAVE:NONE\]/[AUTOSAVE:SEASONAL]/' data/init/d_init.txt && \
    # Fix save dir permissions
    mkdir -p data/save && chmod -R 777 data/save && \
    # Rename bundled libstdc++ to avoid GLU conflicts
    mv libs/libstdc++.so.6 libs/libstdc++.so.6.backup && \
    # Patch dfhack to skip setarch (blocked in Docker)
    sed -i 's/setarch "$setarch_arch" -R env/env/g' dfhack && \
    sed -i 's/setarch "$setarch_arch" -R true/true/g' dfhack && \
    # Enable dfplex
    grep -q "enable dfplex" dfhack.init 2>/dev/null || echo "enable dfplex" >> dfhack.init && \
    # Install DFHack libs system-wide so plugins can find them
    cp hack/libdfhack.so /usr/local/lib/ && \
    cp hack/libdfhack-client.so /usr/local/lib/ && \
    cp hack/liblua.so /usr/local/lib/ && \
    cp hack/libprotobuf-lite.so /usr/local/lib/ && \
    ldconfig && \
    # Fix ownership
    chown -R dfplayer:dfplayer /home/dfplayer/df && \
    chmod +x dfhack libs/Dwarf_Fortress

# ── Screen config: use Ctrl-X instead of Ctrl-A so DF keys work ───────────
RUN echo 'escape ^Xx' > /home/dfplayer/.screenrc && \
    chown dfplayer:dfplayer /home/dfplayer/.screenrc

# ── Terminal client ───────────────────────────────────────────────────────
RUN mkdir -p /usr/local/share/dfplex
COPY dfplex_client.py /usr/local/bin/dfplex
COPY dfplex_client.py /usr/local/share/dfplex/dfplex_client.py
RUN chmod +x /usr/local/bin/dfplex

# ── MOTD ──────────────────────────────────────────────────────────────────
COPY motd /etc/motd

# ── Entrypoint ────────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22 1234 8000

ENTRYPOINT ["/entrypoint.sh"]
