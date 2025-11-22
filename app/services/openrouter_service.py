"""
Service pour interagir avec l'API OpenRouter.
Récupère la liste des modèles disponibles avec leurs coûts et catégories.
"""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1"


class OpenRouterService:
    @staticmethod
    def get_models(api_key: str | None = None) -> list[dict[str, Any]]:
        """
        Récupère la liste des modèles disponibles sur OpenRouter.

        Args:
            api_key: Clé API OpenRouter (optionnelle pour la liste des modèles)

        Returns:
            Liste des modèles avec leurs informations (id, nom, coûts, catégories)
        """
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            response = requests.get(
                f"{OPENROUTER_API_URL}/models",
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            models = data.get("data", [])

            # Transformer et enrichir les données des modèles
            processed_models = []
            for model in models:
                processed_model = {
                    "id": model.get("id", ""),
                    "name": model.get("name", model.get("id", "")),
                    "description": model.get("description", ""),
                    "context_length": model.get("context_length", 0),
                    "pricing": {
                        "prompt": float(model.get("pricing", {}).get("prompt", 0)),
                        "completion": float(model.get("pricing", {}).get("completion", 0)),
                    },
                    "top_provider": model.get("top_provider", {}),
                    "architecture": model.get("architecture", {}),
                }

                # Déterminer les catégories du modèle
                categories = OpenRouterService._categorize_model(model)
                processed_model["categories"] = categories

                processed_models.append(processed_model)

            # Trier par nom
            processed_models.sort(key=lambda x: x["name"].lower())

            logger.info(f"Récupéré {len(processed_models)} modèles OpenRouter")
            return processed_models

        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération des modèles OpenRouter: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            return []

    @staticmethod
    def _categorize_model(model: dict[str, Any]) -> list[str]:
        """
        Détermine les catégories d'un modèle basé sur ses capacités.

        Categories possibles: chat, vision, code, reasoning, free
        """
        categories = []
        model_id = model.get("id", "").lower()
        architecture = model.get("architecture", {})

        # Tous les modèles supportent le chat de base
        categories.append("chat")

        # Détection Vision
        modality = architecture.get("modality", "")
        if "image" in modality or "vision" in model_id or "4o" in model_id:
            categories.append("vision")

        # Détection Code
        code_keywords = ["code", "codestral", "deepseek-coder", "starcoder", "wizard-coder"]
        if any(kw in model_id for kw in code_keywords):
            categories.append("code")

        # Détection Reasoning (modèles avec capacités de raisonnement avancé)
        reasoning_keywords = ["o1", "o3", "reasoning", "think", "r1"]
        if any(kw in model_id for kw in reasoning_keywords):
            categories.append("reasoning")

        # Modèles gratuits
        pricing = model.get("pricing", {})
        prompt_price = float(pricing.get("prompt", 1))
        completion_price = float(pricing.get("completion", 1))
        if prompt_price == 0 and completion_price == 0:
            categories.append("free")

        return categories

    @staticmethod
    def get_models_by_category(
        api_key: str | None = None,
        category: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Récupère les modèles filtrés par catégorie.

        Args:
            api_key: Clé API OpenRouter
            category: Catégorie à filtrer (chat, vision, code, reasoning, free)

        Returns:
            Liste des modèles filtrés
        """
        models = OpenRouterService.get_models(api_key)

        if not category:
            return models

        return [m for m in models if category.lower() in m.get("categories", [])]

    @staticmethod
    def format_price(price_per_token: float) -> str:
        """
        Formate le prix par token en format lisible.

        Args:
            price_per_token: Prix par token (généralement très petit)

        Returns:
            Prix formaté (ex: "$0.50 / 1M tokens")
        """
        if price_per_token == 0:
            return "Gratuit"

        # Prix par million de tokens
        price_per_million = price_per_token * 1_000_000

        if price_per_million < 0.01:
            return f"${price_per_million:.4f} / 1M"
        elif price_per_million < 1:
            return f"${price_per_million:.3f} / 1M"
        else:
            return f"${price_per_million:.2f} / 1M"
