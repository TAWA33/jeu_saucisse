# 🧠 Jeu Saucisse – Jeu multijoueur en réseau

> Un jeu de stratégie en réseau basé sur l’algorithme ELO, développé en Python avec la bibliothèque PodSixNet.

## 📌 Présentation

Le **Jeu Saucisse** est un projet réseau multijoueur permettant à plusieurs joueurs de s’affronter en ligne. Il utilise le module **PodSixNet** pour la communication entre le serveur et les clients, et met en œuvre un système de classement ELO pour suivre la progression des joueurs.

> ⚠️ Ce projet nécessite **Python 3.11**. Les versions plus récentes peuvent être incompatibles avec PodSixNet.

---

## 🚀 Lancer le jeu

### 1. Prérequis

- Python 3.11 (obligatoire)
- PodSixNet (inclus ou à installer si besoin)

### 2. Lancer le serveur

Dans un terminal, lance le serveur avec les paramètres suivants :

```bash
python server.py --port hagrid --key 31425
