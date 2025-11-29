# API Documentation - Module Catalogues Bonial

## Vue d'ensemble

Le module Catalogues permet de consulter les catalogues promotionnels des enseignes discount scrapers depuis Bonial.fr.

**Base URL**: `/api/catalogues`

## Endpoints Publics

### 1. Liste des Enseignes

`GET /api/catalogues/enseignes`

Retourne la liste de toutes les enseignes actives avec le nombre de catalogues en cours.

**Réponse** : `200 OK`
```json
[
  {
    "id": 1,
    "nom": "Gifi",
    "slug_bonial": "Gifi",
    "logo_url": null,
    "couleur": "#E30613",
    "site_url": "https://www.gifi.fr",
    "description": "Décoration, maison, bazar",
    "is_active": true,
    "ordre_affichage": 1,
    "catalogues_actifs_count": 3
  }
]
```

---

### 2. Liste des Catalogues (Paginée)

`GET /api/catalogues`

Retourne la liste paginée des catalogues avec filtres.

**Paramètres Query** :
- `page` (int, default=1): Numéro de page
- `limit` (int, default=20, max=100): Nombre d'éléments par page
- `enseigne_ids` (string, optional): IDs d'enseignes séparés par virgule (ex: `1,2,3`)
- `statut` (string, optional): Filtre par statut (`actif`, `termine`, `tous`)
- `date_debut_min` (datetime, optional): Date de début minimum
- `date_fin_max` (datetime, optional): Date de fin maximum
- `recherche` (string, optional): Recherche dans les titres
- `sort` (string, default=`date_debut`): Tri (`date_debut`, `date_fin`, `enseigne`)
- `order` (string, default=`desc`): Ordre (`asc`, `desc`)

**Réponse** : `200 OK`
```json
{
  "data": [
    {
      "id": 42,
      "enseigne": {
        "id": 1,
        "nom": "Gifi",
        "couleur": "#E30613",
        ...
      },
      "titre": "Catalogue Gifi Noël 2024",
      "date_debut": "2024-11-25T00:00:00",
      "date_fin": "2024-12-24T23:59:59",
      "image_couverture_url": "https://content-media.bonial.biz/...",
      "statut": "actif",
      "nombre_pages": 24,
      "created_at": "2024-11-29T06:00:00"
    }
  ],
  "pagination": {
    "total": 156,
    "page": 1,
    "limit": 20,
    "pages_total": 8
  },
  "metadata": {
    "derniere_mise_a_jour": "2024-11-29T06:15:32"
  }
}
```

---

### 3. Détail d'un Catalogue

`GET /api/catalogues/{catalogue_id}`

Retourne les informations détaillées d'un catalogue.

**Paramètres Path** :
- `catalogue_id` (int): ID du catalogue

**Réponse** : `200 OK`
```json
{
  "id": 42,
  "enseigne": {
    "id": 1,
    "nom": "Gifi",
    ...
  },
  "titre": "Catalogue Gifi Noël 2024",
  "description": null,
  "date_debut": "2024-11-25T00:00:00",
  "date_fin": "2024-12-24T23:59:59",
  "image_couverture_url": "https://content-media.bonial.biz/...",
  "catalogue_url": "https://www.bonial.fr/...",
  "statut": "actif",
  "nombre_pages": 24,
  "metadonnees": null,
  "created_at": "2024-11-29T06:00:00",
  "updated_at": "2024-11-29T06:00:00"
}
```

**Erreurs** :
- `404 Not Found`: Catalogue introuvable

---

### 4. Pages d'un Catalogue

`GET /api/catalogues/{catalogue_id}/pages`

Retourne toutes les pages d'un catalogue, ordonnées par numéro.

**Paramètres Path** :
- `catalogue_id` (int): ID du catalogue

**Réponse** : `200 OK`
```json
[
  {
    "id": 128,
    "numero_page": 1,
    "image_url": "https://content-media.bonial.biz/.../page_1.jpg",
    "image_thumbnail_url": null,
    "largeur": 1200,
    "hauteur": 1600
  },
  {
    "id": 129,
    "numero_page": 2,
    "image_url": "https://content-media.bonial.biz/.../page_2.jpg",
    "image_thumbnail_url": null,
    "largeur": 1200,
    "hauteur": 1600
  }
]
```

**Erreurs** :
- `404 Not Found`: Catalogue introuvable

---

## Endpoints Admin (Authentification requise)

### 5. Déclencher Scraping Manuel

`POST /api/catalogues/admin/scraping/trigger`

Déclenche un scraping manuel des catalogues Bonial.

**Authentification** : Requise (JWT token + rôle `admin`)

**Paramètres Query** :
- `enseigne_id` (int, optional): ID de l'enseigne à scraper. Si omis, scrape toutes les enseignes actives.

**Réponse** : `200 OK`
```json
{
  "success": true,
  "message": "Scraping complete for Gifi",
  "catalogues_trouves": 4,
  "catalogues_nouveaux": 2
}
```

Ou pour toutes les enseignes :
```json
{
  "success": true,
  "message":" Scraping complete for all enseignes",
  "enseignes_processed": 9,
  "catalogues_trouves": 38,
  "catalogues_nouveaux": 12
}
```

**Erreurs** :
- `403 Forbidden`: Accès admin requis
- `404 Not Found`: Enseigne introuvable

---

### 6. Historique des Scraping

`GET /api/catalogues/admin/scraping/logs`

Retourne l'historique des exécutions de scraping.

**Authentification** : Requise (JWT token + rôle `admin`)

**Paramètres Query** :
- `limit` (int, default=50, max=200): Nombre de logs à retourner
- `enseigne_id` (int, optional): Filtre par enseigne
- `statut` (string, optional): Filtre par statut (`success`, `error`, `partial`)

**Réponse** : `200 OK`
```json
[
  {
    "id": 15,
    "date_execution": "2024-11-29T06:00:15",
    "enseigne_id": 1,
    "enseigne_nom": "Gifi",
    "statut": "success",
    "catalogues_trouves": 4,
    "catalogues_nouveaux": 2,
    "catalogues_mis_a_jour": 0,
    "duree_secondes": 45.2,
    "message_erreur": null
  }
]
```

---

### 7. Statistiques de Scraping

`GET /api/catalogues/admin/stats`

Retourne les statistiques globales du module catalogues.

**Authentification** : Requise (JWT token + rôle `admin`)

**Réponse** : `200 OK`
```json
{
  "total_catalogues": 156,
  "catalogues_par_enseigne": {
    "Gifi": 18,
    "Action": 22,
    "Centrakor": 15,
    "La Foir'Fouille": 12,
    "Stokomani": 19,
    "B&M": 14,
    "L'Incroyable": 11,
    "Bazarland": 8,
    "Noz": 17
  },
  "derniere_mise_a_jour": "2024-11-29T06:15:32",
  "prochaine_execution": "Aujourd'hui à 18:00"
}
```

---

## Erreurs Communes

### 400 Bad Request
```json
{
  "detail": "Invalid enseigne_ids format"
}
```

### 403 Forbidden
```json
{
  "detail": "Admin access required"
}
```

### 404 Not Found
```json
{
  "detail": "Catalogue not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Scheduler Automatique

Le scraping est exécuté automatiquement **2 fois par jour** :
- **6h00** : Scraping matinal
- **18h00** : Scraping du soir

Les catalogues sont automatiquement marqués comme `termine` lorsque leur `date_fin` est dépassée.

---

## Notes d'Implémentation

### Détection de Doublons

Le système utilise un hash SHA-256 basé sur :
- `enseigne_id`
- `titre`
- `date_debut`

Cela évite de créer des doublons même si le catalogue est re-scrapé.

### Performance

- Pagination obligatoire (max 100 items/page)
- Index DB sur `enseigne_id`, `date_debut`, `date_fin`, `statut`
- Scraping asynchrone (n'impacte pas les performances API)

### Formats de Date

Toutes les dates sont en **ISO 8601** avec timezone UTC :
```
2024-11-29T06:15:32+00:00
```
