#!/bin/bash
cd "$(dirname "$0")"
clear
echo "Démarrage du serveur local pour prévisualiser le site New Era..."
echo ""

IP=$(ipconfig getifaddr en0 2>/dev/null)
if [ -z "$IP" ]; then
  IP=$(ipconfig getifaddr en1 2>/dev/null)
fi
if [ -z "$IP" ]; then
  IP=$(ifconfig | grep 'inet ' | grep -v 127.0.0.1 | awk '{print $2}' | head -n1)
fi

echo "======================================================"
echo ""
echo "  Sur ton téléphone, connecté au MÊME WiFi que ce Mac,"
echo "  ouvre cette adresse dans le navigateur :"
echo ""
echo "      http://$IP:8000"
echo ""
echo "======================================================"
echo ""
echo "Laisse cette fenêtre ouverte pendant que tu testes."
echo "Pour arrêter le serveur : ferme cette fenêtre ou appuie sur Ctrl+C."
echo ""

python3 -m http.server 8000
