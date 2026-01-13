# Investigation et Correction du Comparateur

## Contexte

Le comparateur de prix récupère parfois des prix incorrects sur certains sites (B&M, L'Incroyable, Gifi, etc.). Il faut identifier les causes (mauvais sélecteurs, parsing regex trop large) et stabiliser l'extraction.

## Focus Actuel

Identification des routes et services impliqués dans la recherche du comparateur.

## Master Plan

- [x] Identifier les services et parsers utilisés par le comparateur
- [x] Identifier les sites posant problème (B&M, Gifi, L'Incroyable, etc.)
- [x] Reproduire les erreurs d'extraction de prix avec des scripts de diagnostic
- [x] Améliorer la logique de `parse_price_text` dans `BaseParser`
- [x] Mettre à jour les sélecteurs CSS spécifiques dans les parsers si nécessaire
- [x] Vérifier les corrections sur une sélection de produits
- [x] Nettoyage et synchronisation Git

## Log de Progression

- [/] Initialisation de la tâche.
