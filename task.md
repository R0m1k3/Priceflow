# Correction Statut Disponibilité Produit B&M

## Contexte

Le produit "Lot de 24 bougies blanches" sur bmstores.fr est affiché comme "Produit retiré du site" dans Priceflow alors qu'il est bien disponible sur le site (0,88€).

## Master Plan

- [x] Correction automatique du statut lors d'un refresh réussi
  - [x] Modifier `_update_db_result` dans `scheduler_service.py` pour remettre `is_available = True` quand un prix est détecté
- [x] Endpoint API pour correction manuelle
  - [x] Ajouter un endpoint `PATCH /{item_id}/availability` dans `items.py` router
  - [x] Permettre de modifier `is_available` via l'API
- [x] Interface utilisateur
  - [x] Ajouter `onMarkAvailable` prop dans `ItemCard.jsx`
  - [x] Ajouter le handler `handleMarkAvailable` dans `Dashboard.jsx`
  - [x] Afficher un bouton "Marquer comme disponible" dans l'overlay des produits indisponibles

## Progress Log

- Diagnostic effectué : produit B&M bien disponible (0,88€) mais marqué indisponible dans la DB
- Modifié `scheduler_service.py` : reset auto de `is_available` quand prix détecté
- Ajouté endpoint API `PATCH /api/items/{id}/availability`
- Ajouté bouton dans l'overlay frontend pour correction manuelle
