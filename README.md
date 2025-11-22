<p align="center">
  <img src="frontend/public/logo.svg" alt="PriceFlow logo" width="120">
</p>

<h1 align="center">PriceFlow</h1>

<p align="center">
  <strong>Suivi de prix intelligent propulse par l'IA</strong>
</p>

<p align="center">
  <a href="#fonctionnalités">Fonctionnalités</a> •
  <a href="#installation">Installation</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#utilisation">Utilisation</a>
</p>

---

## Description

**PriceFlow** est une application auto-hébergée de suivi de prix utilisant l'intelligence artificielle. Elle analyse visuellement les pages produits grâce aux modèles de vision IA (OpenAI, Anthropic, Ollama, OpenRouter) pour détecter les prix et surveiller l'état des stocks.

## Fonctionnalités

- **Analyse par IA** : Utilise les modèles de vision GenAI pour "voir" le prix et l'état du stock sur n'importe quelle page web
- **Multi-fournisseurs IA** : Support de Ollama, OpenAI, Anthropic et **OpenRouter** avec filtres par catégorie (chat, vision, code, raisonnement)
- **Scores de confiance** : L'IA fournit un score de confiance (0-1) pour chaque extraction
- **Historique visuel** : Conserve l'historique des captures d'écran avec les métadonnées IA
- **Défilement intelligent** : Scroll automatique pour charger le contenu différé
- **Notifications** : Support multi-canaux (Discord, Telegram, Email, etc.) via [Apprise](https://github.com/caronc/apprise)
- **Interface en français** : Application entièrement traduite en français
- **Mode sombre** : Interface moderne avec support du thème clair/sombre
- **Dockerisé** : Déploiement facile avec Docker Compose

## Prérequis

- **Docker** et **Docker Compose**
- **Réseau Docker** : `nginx_default` (external)
- **Fournisseur IA** : Clé API OpenAI, Anthropic, OpenRouter, OU une instance Ollama locale

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/R0m1k3/Priceflow.git
cd Priceflow
```

### 2. Créer le réseau Docker (si non existant)

```bash
docker network create nginx_default
```

### 3. Configurer les variables d'environnement

```bash
cp .env.example .env
# Modifier .env selon vos besoins
```

### 4. Lancer l'application

```bash
docker compose up -d
```

### 5. Accéder à l'interface

Ouvrez votre navigateur sur : **http://localhost:8555**

## Architecture Docker

| Service | Port | Description |
|---------|------|-------------|
| **PriceFlow App** | `8555:8555` | Application principale |
| **PostgreSQL** | `5488:5432` | Base de données |
| **Browserless** | `3012:3000` | Navigateur headless pour le scraping |

**Réseau** : `nginx_default` (external)

## Configuration

### Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `DATABASE_URL` | Chaîne de connexion PostgreSQL | `postgresql://priceflow:priceflow@db:5432/priceflow` |
| `BROWSERLESS_URL` | URL WebSocket de Browserless | `ws://browserless:3000` |
| `LOG_LEVEL` | Niveau de log (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `CORS_ORIGINS` | Origines CORS autorisées | `*` |

### Configuration IA

Toute la configuration IA se fait via la page **Paramètres** de l'interface :

**Fournisseurs supportés :**
- **Ollama** : Modèles locaux (gemma3, llava, etc.)
- **OpenAI** : GPT-4o, GPT-4-vision, etc.
- **Anthropic** : Claude 3.5 Sonnet, etc.
- **OpenRouter** : Accès à +200 modèles avec filtres par catégorie

**Paramètres avancés :**
- Température (0.0 - 1.0)
- Tokens maximum
- Seuils de confiance (prix/stock)
- Réparation JSON automatique

### Configuration OpenRouter

1. Sélectionnez **OpenRouter** comme fournisseur
2. Entrez votre clé API (`sk-or-...`)
3. Filtrez les modèles par catégorie :
   - **Chat** : Conversation générale
   - **Vision** : Analyse d'images
   - **Code** : Programmation
   - **Raisonnement** : Raisonnement avancé
   - **Gratuit** : Modèles gratuits
4. Sélectionnez un modèle avec affichage des coûts

### Notifications

Créez des **Profils de notification** dans les Paramètres avec des URLs Apprise :

```
# Discord
discord://webhook_id/webhook_token

# Telegram
tgram://bot_token/chat_id

# Email
mailto://user:password@gmail.com
```

## Utilisation

### Ajouter un article à suivre

1. Cliquez sur **Ajouter un article**
2. Entrez l'URL de la page produit
3. (Optionnel) Définissez un prix cible
4. (Optionnel) Associez un profil de notification
5. Enregistrez

### Fonctionnement

1. PriceFlow capture une image de la page produit
2. L'IA analyse l'image pour extraire le prix et l'état du stock
3. Les données sont enregistrées avec un score de confiance
4. Si le prix atteint votre cible, vous êtes notifié

## Structure du projet

```
Priceflow/
├── app/                    # Backend FastAPI
│   ├── routers/           # Endpoints API
│   ├── services/          # Services métier
│   └── models.py          # Modèles SQLAlchemy
├── frontend/              # Frontend React
│   ├── src/
│   │   ├── components/    # Composants React
│   │   ├── pages/         # Pages (Dashboard, Settings)
│   │   └── i18n/          # Traductions
│   └── public/            # Assets statiques
├── docker-compose.yml     # Configuration Docker
├── Dockerfile            # Image Docker
├── init.sql              # Script d'initialisation DB
└── .env.example          # Variables d'environnement
```

## Personnalisation

### Changer le favicon

Remplacez les fichiers dans `/frontend/public/` :
- `favicon.ico` (32x32 ou 64x64)
- `apple-touch-icon.png` (180x180)
- `logo.png` (logo principal)

### Ajouter une langue

1. Créez un fichier dans `frontend/src/i18n/locales/`
2. Copiez la structure de `fr.json`
3. Modifiez `frontend/src/i18n/index.js`

## Développement

### Lancer en mode développement

```bash
# Backend
cd app
uvicorn app.main:app --reload --port 8555

# Frontend
cd frontend
npm install
npm run dev
```

### Migrations de base de données

```bash
# Créer une migration
alembic revision --autogenerate -m "description"

# Appliquer les migrations
alembic upgrade head
```

## Licence

Ce projet est sous licence GNU General Public License v3.0 - voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

<p align="center">
  Développé avec ❤️ pour le suivi de prix intelligent
</p>
