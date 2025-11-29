# Guide de Démarrage - Priceflow

## Problème détecté

- ❌ Docker non installé/accessible
- ❌ WSL non installé
- ❌ Application non démarrée (port 8555 fermé)

## Solutions possibles

### Option 1 : Installer Docker Desktop (Recommandé)

1. Télécharger Docker Desktop : https://www.docker.com/products/docker-desktop/
2. Installer et démarrer Docker Desktop
3. Ouvrir un terminal PowerShell dans `C:\Users\Michael\Git\Priceflow`
4. Lancer l'application :
   ```bash
   docker compose up -d
   ```
5. Vérifier les logs :
   ```bash
   docker compose logs api | Select-String "site(s)"
   ```
   Vous devriez voir : **"10 site(s) de recherche créé(s)"**

### Option 2 : Installer WSL + Docker

1. Installer WSL :
   ```powershell
   wsl --install
   ```
2. Redémarrer l'ordinateur
3. Installer Docker dans WSL
4. Suivre les étapes de l'Option 1

### Option 3 : Application déjà démarrée ailleurs

Si l'application tourne déjà dans un conteneur ou processus différent :

1. Vérifier les processus :
   ```powershell
   Get-Process | Where-Object {$_.ProcessName -like "*python*" -or $_.ProcessName -like "*uvicorn*"}
   ```

2. Vérifier les ports ouverts :
   ```powershell
   netstat -ano | findstr :8555
   ```

## Prochaines étapes après démarrage

1. ✅ Vérifier que 10 sites sont seedés (logs)
2. ✅ Tester via script : `docker compose exec api python verify_all_sites.py`
3. ✅ Tester via interface : http://localhost:8555/search

## État actuel

**Application : ❌ NON DÉMARRÉE**

- Configuration : ✅ 10 sites ajoutés dans `search_config.py`
- Script de test : ✅ `verify_all_sites.py` créé
- Tests : ⏸️ En attente du démarrage de l'application
