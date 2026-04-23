FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

# ── Runtime deps ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    openssh-server \
    screen \
    sudo \
    python3 python3-pip \
    libsdl1.2debian \
    libsdl-image1.2 \
    libsdl-ttf2.0-0 \
    libgtk2.0-0 \
    libglu1-mesa \
    libopenal1 \
    libsndfile1 \
    libncurses5 \
    libncursesw5 \
    wget unzip curl \
    && rm -rf /var/lib/apt/lists/*

# ncurses symlinks DF needs at runtime
RUN ln -sf /lib/x86_64-linux-gnu/libncursesw.so.5 /lib/x86_64-linux-gnu/libncursesw.so.6 2>/dev/null || true && \
    ln -sf /lib/x86_64-linux-gnu/libncurses.so.5  /lib/x86_64-linux-gnu/libncurses.so.6  2>/dev/null || true && \
    ldconfig

RUN pip3 install websocket-client

# ── SSH setup ─────────────────────────────────────────────────────────────
RUN mkdir /var/run/sshd
RUN useradd -ms /bin/bash dfplayer && \
    echo 'dfplayer:dwarves' | chpasswd && \
    usermod -aG sudo dfplayer && \
    echo 'dfplayer ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    echo "PrintLastLog no" >> /etc/ssh/sshd_config && \
    echo "PrintMotd yes"   >> /etc/ssh/sshd_config

# ── DF + DFHack + DFPlex bundle ───────────────────────────────────────────
COPY df_bundle/ /home/dfplayer/df/
RUN chown -R dfplayer:dfplayer /home/dfplayer/df/ && \
    chmod +x /home/dfplayer/df/dfhack && \
    chmod +x /home/dfplayer/df/libs/Dwarf_Fortress

# Force TEXT mode (no display in container)
RUN sed -i 's/\[PRINT_MODE:2D\]/[PRINT_MODE:TEXT]/' /home/dfplayer/df/data/init/init.txt

# Fix save directory permissions
RUN mkdir -p /home/dfplayer/df/data/save && \
    chmod -R 777 /home/dfplayer/df/data/save

# Rename DF's bundled libstdc++ so system's newer version is used
RUN mv /home/dfplayer/df/libs/libstdc++.so.6 /home/dfplayer/df/libs/libstdc++.so.6.backup 2>/dev/null || true

# Patch dfhack to skip setarch (blocked in Docker)
RUN sed -i 's/setarch "$setarch_arch" -R env/env/g' /home/dfplayer/df/dfhack && \
    sed -i 's/setarch "$setarch_arch" -R true/true/g' /home/dfplayer/df/dfhack

# Enable dfplex plugin
RUN grep -q "enable dfplex" /home/dfplayer/df/dfhack.init 2>/dev/null || \
    echo "enable dfplex" >> /home/dfplayer/df/dfhack.init

# ── Terminal client ───────────────────────────────────────────────────────
COPY dfplex_client.py /usr/local/bin/dfplex
RUN chmod +x /usr/local/bin/dfplex

# ── MOTD ──────────────────────────────────────────────────────────────────
COPY motd /etc/motd

# ── Entrypoint ────────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22 1234 8000

ENTRYPOINT ["/entrypoint.sh"]
