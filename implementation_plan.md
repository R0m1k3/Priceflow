# Plan d'Implémentation - Correctifs de Sécurité et Performance

Ce plan vise à résoudre les vulnérabilités critiques et les goulots d'étranglement de performance identifiés dans le rapport d'analyse technique.

## User Review Required

> [!IMPORTANT]
> **Action Utilisateur Requise :** Vous devrez créer un fichier `.env` à la racine du projet en copiant `.env.example` et en y insérant vos vrais secrets (API Keys, Mots de passe). Je ne peux pas connaître vos mots de passe sécurisés.

> [!WARNING]
> **Changement de Configuration :** Le fichier `docker-compose.yml` sera modifié pour ne plus contenir de secrets en clair. Le redémarrage des conteneurs sera nécessaire.

## Proposed Changes

### Configuration & Sécurité

#### [NEW] [.env.example](file:///c:/Users/Jacques/Git/Priceflow-1/.env.example)
- Création d'un modèle de fichier d'environnement documentant toutes les variables requises.

#### [MODIFY] [docker-compose.yml](file:///c:/Users/Jacques/Git/Priceflow-1/docker-compose.yml)
- Remplacement des valeurs harcodées par `${VARIABLE}`.
- Suppression de la clé API OpenRouter en clair.
- Suppression du mot de passe DB en clair.

#### [MODIFY] [app/main.py](file:///c:/Users/Jacques/Git/Priceflow-1/app/main.py)
- Restriction de la configuration CORS.
- Chargement sécurisé de la configuration.

### Efficience & Performance

#### [MODIFY] [app/services/improved_search_service.py](file:///c:/Users/Jacques/Git/Priceflow-1/app/services/improved_search_service.py)
- **Problème :** Appels DB bloquants (`db.query`) dans une fonction `async`.
- **Solution :** Mettre les appels DB dans un threadpool pour ne pas bloquer la boucle d'événements principale.
- **Détail :** Utilisation de `fastapi.concurrency.run_in_threadpool` pour encapsuler les accès DB synchrones.

#### [MODIFY] [app/routers/search.py](file:///c:/Users/Jacques/Git/Priceflow-1/app/routers/search.py)
- Adaptation de l'appel au service pour gérer correctement l'asynchronisme.

## Verification Plan

### Automated Tests
- Vérification que l'application démarre avec les variables d'environnement.
- Test de charge léger sur l'endpoint de recherche pour confirmer que l'interface ne "gèle" pas pendant le chargement (grâce au fix async).

### Manual Verification
- Vérifier que `docker-compose config` n'affiche plus de secrets.
- Vérifier les logs pour confirmer le chargement correct de la configuration.
