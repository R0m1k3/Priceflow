"""
Router pour les endpoints OpenRouter.
Permet de récupérer la liste des modèles et leurs coûts.
"""

from fastapi import APIRouter, Query

from app.services.openrouter_service import OpenRouterService

router = APIRouter(prefix="/openrouter", tags=["openrouter"])


@router.get("/models")
def get_openrouter_models(
    api_key: str | None = Query(None, description="Clé API OpenRouter (optionnelle)"),
    category: str | None = Query(None, description="Filtrer par catégorie: chat, vision, code, reasoning, free")
):
    """
    Récupère la liste des modèles OpenRouter disponibles.

    - **api_key**: Clé API OpenRouter (optionnelle pour la liste publique)
    - **category**: Filtrer par catégorie (chat, vision, code, reasoning, free)

    Retourne la liste des modèles avec:
    - id: Identifiant du modèle
    - name: Nom affiché
    - description: Description du modèle
    - context_length: Longueur de contexte maximale
    - pricing: Coûts (prompt et completion par token)
    - categories: Liste des catégories du modèle
    """
    if category:
        models = OpenRouterService.get_models_by_category(api_key, category)
    else:
        models = OpenRouterService.get_models(api_key)

    return {
        "models": models,
        "total": len(models),
        "categories": ["chat", "vision", "code", "reasoning", "free"]
    }


@router.get("/categories")
def get_categories():
    """
    Retourne la liste des catégories disponibles pour filtrer les modèles.
    """
    return {
        "categories": [
            {"id": "chat", "name": "Chat", "description": "Modèles de conversation générale"},
            {"id": "vision", "name": "Vision", "description": "Modèles avec capacités d'analyse d'images"},
            {"id": "code", "name": "Code", "description": "Modèles spécialisés en programmation"},
            {"id": "reasoning", "name": "Raisonnement", "description": "Modèles avec capacités de raisonnement avancé"},
            {"id": "free", "name": "Gratuit", "description": "Modèles gratuits"}
        ]
    }
