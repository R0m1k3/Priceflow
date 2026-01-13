# Investigation et Correction du Statut "Produit Retiré"

## Contexte

Le système de suivi des prix marquait incorrectement certains produits comme "retirés" alors qu'ils étaient toujours disponibles, souvent à cause de blocages (bot detection) ou de changements mineurs de titre.

## Focus Actuel

Finalisation et vérification.

## Master Plan

- [x] Analyser la logique de comparaison de titres dans `app/services/scheduler_service.py`
- [x] Vérifier si les scrapers extraient correctement les titres lors des mises à jour
- [x] Identifier les cas limites (edge cases) où la similarité de titre échoue
- [x] Corriger la logique pour éviter les faux positifs d'indisponibilité
- [x] Vérifier la correction avec un exemple concret (test_logic.py)
- [x] Implémenter le reset automatique de disponibilité si un prix est trouvé

## Log de Progression

- [x] Investigation terminée : identification des faux positifs dus aux titres de blocage (Cloudflare, etc.) et aux placeholders ("Loading").
- [x] Logique de normalisation renforcée.
- [x] Détection des bots ajoutée pour tous les sites.
- [x] Auto-reset de `is_available` implémenté dans `_update_db_result`.
- [x] Correction déployée dans `scheduler_service.py`.
- [x] Affinage de la détection de bot pour Stokomani/L'Incroyable (détection conditionnelle au titre).
- [x] Support des versions "V2" et matching par mots pour les noms courts sur Amazon.
- [x] Sécurisation du flux Action.com (check d'indisponibilité déplacé après le titre).
