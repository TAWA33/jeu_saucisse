# 🧠 Jeu Saucisse – Jeu multijoueur en réseau

Jeu réalisé dans le cadre d'un projet d'informatique du **CPBx (Université de Bordeaux** - Année 2024/2025
> Un jeu de stratégie en réseau basé sur l’algorithme ELO, développé en Python avec la bibliothèque PodSixNet.

## 👥 Auteurs
- Kitchi-Tawa BOURGUINAT
- Nathan GRAVIER
- Hugo PALOS

## 📁 Contenu du dépôt

- 📄 Documentation utilisateur
- 📃 Rapport
- 🐍 Fichier client et Serveur

## 📌 Présentation

Le **Jeu Saucisse** est un projet réseau multijoueur permettant à plusieurs joueurs de s’affronter en ligne. Il utilise le module **PodSixNet** pour la communication entre le serveur et les clients, et met en œuvre un système de classement ELO pour suivre la progression des joueurs.

> ⚠️ Ce projet nécessite **Python 3.11**. Les versions plus récentes peuvent être incompatibles avec PodSixNet.


---

## 🚀 Lancer le jeu

### 1. Prérequis

- Python 3.11 (obligatoire)
- PodSixNet (inclus ou à installer si besoin)

### 2. Lancer le serveur

Dans un terminal, lance le serveur avec les paramètres suivants : (bash) python server.py --port hagrid --key 31425

### 3. Rejoindre le lobby (client)

Dans un autre terminal, exécute : python clientB.py
- Indique ton nom ou pseudo pour te connecter.
- Tu accèdes alors au lobby, où sont listés les joueurs disponibles.

## 🎮 Jouer une partie

- Clique sur un joueur pour l’inviter à jouer.
- Si la différence d’ELO est trop grande, une alerte s’affichera.
- Si l’invitation est acceptée, la partie commence automatiquement.
- À la fin d’une partie (ou si un joueur quitte), les ELO sont mis à jour et vous retournez dans le lobby.
