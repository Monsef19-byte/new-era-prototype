#!/bin/bash
cd "$(dirname "$0")"
clear
echo "======================================================"
echo ""
echo "  Panneau d'administration New Era"
echo ""
echo "  Démarrage en cours..."
echo "  Ton navigateur va s'ouvrir automatiquement."
echo ""
echo "  Laisse cette fenêtre ouverte pendant que tu utilises"
echo "  le panneau. Pour l'arrêter : ferme cette fenêtre"
echo "  ou appuie sur Ctrl+C."
echo ""
echo "======================================================"
echo ""

python3 server.py
