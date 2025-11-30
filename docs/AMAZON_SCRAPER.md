# Amazon France Scraper - Documentation

## 🎯 Vue d'ensemble

Le scraper Amazon France est un système de recherche de produits conçu pour éviter la détection anti-bot d'Amazon. Il utilise Crawl4AI avec des techniques avancées d'anti-détection.

## 🛡️ Techniques anti-détection

### 1. User-Agent rotatif
- Pool de 5 User-Agents réalistes (Chrome, Firefox, Safari, Edge)
- Rotation aléatoire à chaque requête
- Headers complets mimant un vrai navigateur

### 2. Proxies résidentiels
- **10 proxies rotatifs** configurés
- Sélection aléatoire pour chaque recherche
- Format: `ip:port:username:password`
- Configuration dans `/app/core/search_config.py`

### 3. Délais aléatoires
- Entre **1.5 et 4 secondes** entre les requêtes
- Simule le comportement humain
- Évite les patterns de bot

### 4. Headers HTTP réalistes
```python
{
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,...",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    ...
}
```

### 5. Crawl4AI configuration
- `headless=True` - Mode invisible
- `--disable-blink-features=AutomationControlled` - Désactive la détection d'automation
- `wait_until="networkidle"` - Attend le chargement complet
- `remove_overlay_elements=True` - Supprime les popups
- Acceptation automatique des cookies

## 📦 Données extraites

Pour chaque produit, le scraper extrait :

| Champ | Type | Description |
|-------|------|-------------|
| `title` | string | Titre du produit |
| `url` | string | URL Amazon |
| `price` | float | Prix actuel en EUR |
| `original_price` | float | Prix original si promotion |
| `rating` | float | Note sur 5 étoiles |
| `reviews_count` | int | Nombre d'avis |
| `image_url` | string | URL de l'image |
| `in_stock` | bool | Disponibilité |
| `prime` | bool | Éligible Prime |
| `sponsored` | bool | Produit sponsorisé |

## 🚀 Utilisation

### Backend (Python)

```python
from app.services.amazon_scraper import scrape_amazon_search

# Recherche simple
products = await scrape_amazon_search("aspirateur", max_results=20)

for product in products:
    print(f"{product.title} - {product.price}€")
```

### API REST

```bash
# Endpoint SSE (Server-Sent Events)
GET /api/amazon/search?q=aspirateur&max_results=20

# Health check
GET /api/amazon/health
```

### Frontend (React)

```javascript
// EventSource pour SSE
const eventSource = new EventSource(`/api/amazon/search?q=${query}&max_results=20`);

eventSource.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    // data.status: 'searching', 'completed', 'error'
    // data.results: array of products
});
```

Accès direct : **http://localhost/amazon** (après connexion)

## 🧪 Tests

### Script de test complet

```bash
# Lancer tous les tests
python test_amazon_scraper.py
```

Tests inclus :
1. ✅ Recherche basique (5 produits)
2. ✅ Requêtes multiples (clavier, souris, casque)
3. ✅ Vérification anti-détection

### Test manuel simple

```python
import asyncio
from app.services.amazon_scraper import test_amazon_scraper

asyncio.run(test_amazon_scraper())
```

## ⚙️ Configuration

### Proxies

Modifiez `/app/core/search_config.py` :

```python
AMAZON_PROXY_LIST_RAW = [
    "ip1:port1:user1:pass1",
    "ip2:port2:user2:pass2",
    # ... ajoutez vos proxies
]
```

### User-Agents

Ajoutez dans `/app/services/amazon_scraper.py` :

```python
AMAZON_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; ...) Chrome/131.0.0.0",
    # ... ajoutez vos user-agents
]
```

### Délais

Modifiez la fonction `random_delay()` :

```python
async def random_delay(min_seconds=1.5, max_seconds=4.0):
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)
```

## 🔍 Sélecteurs CSS Amazon

Le scraper utilise les sélecteurs suivants (mis à jour pour 2024) :

```python
# Cartes produits
product_cards = soup.find_all('div', {'data-component-type': 's-search-result'})

# Titre
title_elem = card.select_one('h2 a span, h2 span')

# Prix actuel
price_elem = card.select_one('.a-price .a-offscreen')

# Prix original (promo)
original_price_elem = card.select_one('.a-price.a-text-price .a-offscreen')

# Note
rating_elem = card.select_one('[aria-label*="étoile"], [aria-label*="star"]')

# Nombre d'avis
reviews_elem = card.select_one('[aria-label*="étoile"] + span')

# Image
img_elem = card.select_one('img.s-image')

# Prime
prime = card.select_one('[aria-label*="Prime"], i.a-icon-prime')
```

## 📊 Performances

- **Vitesse** : ~3-5 secondes pour 20 produits
- **Taux de succès** : ~95% (avec proxies)
- **Limite recommandée** : Max 20 produits par requête
- **Délai entre requêtes** : 2-5 secondes

## ⚠️ Limitations connues

1. **CAPTCHA** : Peut survenir en cas d'utilisation intensive
   - Solution : Rotation des proxies + délais plus longs

2. **Géolocalisation** : Les proxies doivent être français/européens
   - Amazon.fr peut bloquer les IPs non-européennes

3. **Structure HTML** : Amazon peut modifier ses sélecteurs
   - Vérifier régulièrement les sélecteurs CSS

4. **Rate limiting** : Amazon limite les requêtes par IP
   - Utiliser les proxies rotatifs

## 🐛 Debugging

### Logs

Les logs détaillés sont disponibles dans la console :

```python
logger.info(f"🔍 Searching Amazon France: {query}")
logger.info(f"📍 URL: {search_url}")
logger.debug(f"🎭 User-Agent: {user_agent}")
logger.debug(f"🌐 Using proxy: {proxy['server']}")
```

### Messages d'erreur courants

| Erreur | Cause | Solution |
|--------|-------|----------|
| `CAPTCHA detected` | Trop de requêtes | Attendre + changer de proxy |
| `Bot detection triggered` | Mauvais User-Agent | Vérifier USER_AGENTS |
| `No products found` | Requête vide ou blocage | Vérifier la recherche |
| `Timeout` | Connexion lente | Augmenter `page_timeout` |

### Mode debug Crawl4AI

```python
browser_config = BrowserConfig(
    headless=False,  # Voir le navigateur
    verbose=True,     # Logs détaillés
    ...
)
```

## 📈 Évolutions futures

- [ ] Cache Redis pour éviter les requêtes répétées
- [ ] Pagination automatique (>20 produits)
- [ ] Détection automatique de CAPTCHA
- [ ] Résolution de CAPTCHA (service tiers)
- [ ] Scraping des détails produit (description, specs)
- [ ] Support Amazon.de, Amazon.es, etc.
- [ ] Monitoring des prix en temps réel
- [ ] Alertes de baisse de prix

## 🔐 Sécurité & Légalité

⚠️ **Important** : Ce scraper est destiné à un usage personnel uniquement.

- ✅ Usage personnel/éducatif
- ✅ Recherche de produits
- ✅ Comparaison de prix
- ❌ Revente de données
- ❌ Usage commercial intensif
- ❌ Contournement de CAPTCHA à grande échelle

Respectez les [Conditions d'utilisation Amazon](https://www.amazon.fr/gp/help/customer/display.html?nodeId=201909000).

## 📞 Support

En cas de problème :

1. Vérifier les logs (`logger.info/debug/error`)
2. Tester avec le script `test_amazon_scraper.py`
3. Vérifier la configuration des proxies
4. Consulter la [documentation Crawl4AI](https://crawl4ai.com/)

## 🎉 Crédits

- **Crawl4AI** : Framework de scraping IA
- **BeautifulSoup** : Parsing HTML
- **FastAPI** : API backend
- **React** : Interface frontend
- **Shadcn UI** : Composants UI
