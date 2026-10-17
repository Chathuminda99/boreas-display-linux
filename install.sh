#!/usr/bin/env bash
# Per-user install of boreas-display-linux. The udev rule step needs sudo.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

SHARE="$HOME/.local/share/boreas-display"
BIN="$HOME/.local/bin"
CONF="$HOME/.config/boreas-display"

remove_legacy() {
    # Earlier versions of this project were installed as "zeus-cast".
    if [[ -e "$BIN/zeus-cast" || -e "$HOME/.config/systemd/user/zeus-cast.service" ]]; then
        echo "==> Removing old zeus-cast install"
        systemctl --user disable --now zeus-cast.service 2>/dev/null || true
        rm -rf "$HOME/.local/share/zeus-cast" "$BIN/zeus-cast" \
               "$HOME/.config/systemd/user/zeus-cast.service" \
               "$HOME/.local/share/applications/zeus-cast.desktop" \
               "$HOME/.local/share/icons/hicolor/256x256/apps/zeus-cast.png"
    fi
    if [[ -d "$HOME/.config/zeus-cast" && ! -e "$CONF" ]]; then
        mv "$HOME/.config/zeus-cast" "$CONF"
    fi
}

if [[ "${1:-}" == "--uninstall" ]]; then
    systemctl --user disable --now boreas-display.service 2>/dev/null || true
    rm -rf "$SHARE" "$BIN/boreas-display" "$HOME/.config/systemd/user/boreas-display.service" \
           "$HOME/.local/share/applications/boreas-display.desktop" \
           "$HOME/.local/share/icons/hicolor/256x256/apps/boreas-display.png"
    systemctl --user daemon-reload
    sudo rm -f /etc/udev/rules.d/70-gamdias-boreas.rules && sudo udevadm control --reload
    echo "Uninstalled (settings kept in $CONF)."
    exit 0
fi

remove_legacy

echo "==> Installing files to $SHARE"
rm -rf "$SHARE"
mkdir -p "$SHARE" "$BIN" "$HOME/.config/systemd/user" "$HOME/.local/share/applications"
cp -r boreas_display "$SHARE/"
install -m755 boreas-display "$BIN/boreas-display"
install -m644 data/boreas-display.service "$HOME/.config/systemd/user/"
install -m644 data/boreas-display.desktop "$HOME/.local/share/applications/"
if [[ -f data/boreas-display.png ]]; then
    install -Dm644 data/boreas-display.png "$HOME/.local/share/icons/hicolor/256x256/apps/boreas-display.png"
fi

echo "==> Installing udev rule (sudo)"
sudo install -m644 data/70-gamdias-boreas.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw --action=change

echo "==> Enabling background service"
systemctl --user daemon-reload
systemctl --user enable --now boreas-display.service

echo
"$BIN/boreas-display" list || true
echo
echo "Done. Open 'BOREAS Display' from your app menu, or run: boreas-display gui"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Note: add $BIN to your PATH.";; esac
