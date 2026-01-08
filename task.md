# Correction Statut Disponibilité Produit

## Contexte

Le produit "Lot de 24 bougies blanches" sur bmstores.fr est affiché comme "Produit retiré du site" alors qu'il est bien disponible.

## Logique Implémentée

**Détection d'indisponibilité :**

- Si le **titre de la page a changé** significativement par rapport au nom stocké → le produit original a été remplacé → marquer comme "Produit remplacé"
- Exemple: URL `/produit/123-bougies-blanches` maintenant affiche "Bougies Multicolores" → produit indisponible

**Reset de disponibilité :**

- Si le **titre correspond toujours** au nom stocké → le produit existe encore → remettre `is_available = true`

## Tâches Complétées

- [x] Fonction `_normalize_title()` - normalise les titres pour comparaison
- [x] Fonction `_titles_match()` - compare les titres avec similarité Jaccard
- [x] Détection de remplacement de produit dans `process_item_check()`
- [x] Reset automatique quand le titre correspond
- [x] Endpoint API `PATCH /{item_id}/availability` pour correction manuelle
- [x] Bouton "Marquer comme disponible" dans l'interface

## Fichiers Modifiés

- `app/services/scheduler_service.py` - logique de détection
- `app/routers/items.py` - endpoint API
- `frontend/src/pages/Dashboard.jsx` - handler
- `frontend/src/components/dashboard/ItemCard.jsx` - bouton UI
