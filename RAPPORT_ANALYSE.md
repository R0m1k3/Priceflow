# Rapport d'Analyse Technique - PriceFlow

**Date:** 07 Janvier 2026
**Analyste:** Mary (Business Analyst)
**Application:** PriceFlow (Backend & Scrapers)

## 1. Synthèse "Executive Summary"

L'application **PriceFlow** présente des fondations fonctionnelles solides pour le scraping e-commerce, utilisant des technologies modernes (Playwright, FastAPI, Browserless). L'architecture de scraping est particulièrement sophistiquée, utilisant des navigateurs persistants et des stratégies hybrides d'extraction (JSON-LD, CSS, IA).

Cependant, l'analyse révèle des **failles de sécurité critiques** (clés API exposées) et des **problèmes de performance structurels** (blocage de la boucle événementielle asynchrone par la base de données) qui doivent être corrigés avant tout passage en production.

---

## 2. Analyse Sécurité 🚨 (CRITIQUE)

### 🔴 Failles Critiques
1.  **Exposition de Secrets (Hardcoded Secrets) :**
    *   **Fichier :** `docker-compose.yml`
    *   **Problème :** La clé `OPENROUTER_API_KEY` est écrite en clair.
    *   **Risque :** Utilisation frauduleuse du quota, surcoût financier immédiat.
    *   **Action requise :** Révoquer la clé immédiatement et utiliser un fichier `.env`.

2.  **Identifiants par Défaut :**
    *   **Fichier :** `docker-compose.yml`
    *   **Problème :** `POSTGRES_PASSWORD=priceflow` est utilisé.
    *   **Risque :** Compromission triviale de la base de données si le port 5488 est exposé (ce qui est le cas dans la config actuelle).

3.  **CORS Permissif (Cross-Origin Resource Sharing) :**
    *   **Fichier :** `main.py`
    *   **Problème :** `allow_origins=["*"]` (ou via variable d'env par défaut).
    *   **Risque :** Permet à n'importe quel site malveillant d'interroger l'API s'il est visité par un utilisateur authentifié (CSRF/Data Exfiltration).

### 🟠 Risques Modérés
1.  **Migrations Manuelles Hardcodées :**
    *   **Fichier :** `main.py`
    *   **Problème :** Utilisation de `CREATE TABLE` via des chaînes SQL brutes au démarrage.
    *   **Risque :** Difficile à maintenir, risque d'erreur humaine et d'injection si les chaînes étaient dynamiques. `alembic` est installé mais non utilisé pour l'initialisation.

2.  **CSP Browserless désactivé :**
    *   Le service Browserless désactive explicitement la Content Security Policy (`bypass_csp: true`). C'est nécessaire pour le scraping mais nécessite que le conteneur soit strictement isolé du réseau interne sensible.

---

## 3. Analyse Efficience ⚡

### ✅ Points Forts
1.  **Browserless Persistant :** L'utilisation de `async_playwright` avec une connexion WebSocket persistante vers Browserless (`BrowserlessService`) est excellente. Cela évite le coût énorme du lancement de processus Chrome pour chaque requête.
2.  **Streaming SSE :** L'endpoint de recherche (`/api/search`) utilise les Server-Sent Events, permettant une UX réactive même si le scraping est lent.

### ⚠️ Problèmes de Performance (Blocking I/O)
1.  **Mélange Synchrone/Asynchrone Dangereux :**
    *   **Fichier :** `app/services/improved_search_service.py` (et autres routeurs)
    *   **Détection :** La fonction `search_products` est définie avec `async def`, mais elle effectue des appels base de données synchrones : `db.query(SearchSite)...all()`.
    *   **Impact :** **Ceci bloque la boucle d'événements (Event Loop) de FastAPI.** Pendant que la base de données répond, *aucune* autre requête API ne peut être traitée. Sous charge, cela effondrera les performances.
    *   **Solution :** Utiliser `run_in_threadpool` pour les appels DB synchrones ou migrer vers `SQLAlchemy AsyncSession`.

---

## 4. Analyse Efficacité & Fonctionnalités 🎯

### ✅ Points Forts
1.  **Stratégie de Scraping Robuste ("ImprovedSearchService") :**
    *   Le code implémente une stratégie en "couches" très intelligente :
        1.  **JSON-LD** (Structuré, très fiable).
        2.  **IA Extraction** (Fallback puissant si configuré).
        3.  **Sélecteurs CSS Stricts** (Meta tags, ID connus).
        4.  **Sélecteurs CSS Flous** (Recherche du prix le plus bas, détection de mots clés "HT/TTC").
    *   Cette redondance garantit un taux de succès élevé.
2.  **Gestion des Anti-Bots :**
    *   Rotation des User-Agents.
    *   Injection de scripts "Stealth" (masquage de `navigator.webdriver`).
    *   Gestion automatique des popups (CMP/Cookies).

### ⚠️ Améliorations Possibles
1.  **Gestion des Erreurs :**
    *   Les exceptions sont souvent capturées génériquement (`except Exception: pass`). Cela peut masquer des changements structurels sur les sites cibles.

---

## 5. Qualité du Code 📝

### ✅ Points Positifs
*   Utilisation du typage statique (Type Hints) généralisée.
*   Utilisation de `ruff` pour le linting.
*   Code modulaire (Routeurs / Services / Schémas).

### ⚠️ Dette Technique
1.  **God Classes :**
    *   `BrowserlessService` (~700 lignes) et `ImprovedSearchService` (~950 lignes) cumulent trop de responsabilités (gestion navigateur, parsing, logique métier).
    *   Il serait préférable de séparer le "BrowserManager" des "Parsers".
2.  **Duplication de Code :**
    *   Redondance entre `browserless_service.py` et `improved_search_service.py` sur l'initialisation et la gestion des popups.

## Recommandations Prioritaires

1.  **IMMÉDIAT (Sécurité) :** Passer `OPENROUTER_API_KEY` et les mots de passe DB dans un fichier `.env`.
2.  **COURT TERME (Performance) :** Corriger les appels DB bloquants dans les routes `async`.
3.  **MOYEN TERME (Code) :** Refactoriser pour éliminer la duplication entre les services de scraping.
