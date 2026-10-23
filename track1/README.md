# RYO-CHAN Track 01 - agent de recherche et recus rejouables

Petit prototype Python pour appeler un outil de recherche **en lecture seule** de RYO-CHAN, conserver la reponse comme preuve, et rejouer les decisions sans rappeler le service. Il n'envoie aucun ordre et ne touche a aucun fonds.

## Configuration

Le client utilise MCP Streamable HTTP. Definissez la cle communiquee par les organisateurs (ne la commitez jamais) :

```powershell
$env:RYO_MCP_KEY = "votre cle"
$env:RYO_SYMBOL = "BTC"
py agent.py
```

Par defaut, le client utilise `https://app-ryochan.com/api/mcp` et l'outil `market_overview`. `RYO_MCP_URL` permet de remplacer l'URL. L'appel est en lecture seule. Sans cle, ou si l'appel echoue, une ligne `NO_DATA` explicite est conservee; aucune valeur de marche de remplacement n'est fabriquee.

## Recus et rejeu

Chaque ligne de `journal.jsonl` conserve l'horodatage de reception, l'outil, ses parametres, l'horodatage de demande, la reponse source complete ou son erreur, la decision, le hash du recu et le hash precedent. Pour verifier le journal hors ligne :

```powershell
py agent.py replay
```

Le rejeu recalcule les decisions depuis les preuves enregistrees et verifie les liens de hash. Les anciennes lignes non chainees au format d'origine restent verifiables, mais ne gagnent pas retroactivement de lien precedent. Un chainage local detecte les incoherences et suppressions internes au fichier; il ne constitue pas une signature externe et ne protege pas contre la reecriture coordonnee de tout le journal.

## Decision actuelle et limites

Une reponse RYO valide mene a `REVIEW`, pas a un achat ou une vente : le schema public detaille de `market_overview` n'a pas pu etre confirme ici et le client ne suppose donc ni champ de prix ni serie temporelle. Une source indisponible mene a `NO_DATA`. Avant d'activer une strategie de trades fictifs, il faut verifier la reponse reelle de l'outil, selectionner les champs de prix dont la provenance est explicite, puis definir une strategie deterministe, les entrees/sorties et le calcul PnL. Le journal conserve des maintenant les preuves et erreurs pour permettre cet audit.

## Bibliotheques

Python standard uniquement : `hashlib`, `json`, `os`, `sys`, `time`, `urllib.error` et `urllib.request`. Aucune dependance externe, aucun LLM.

## Sources consultees

- [Page officielle RYO-CHAN Hackathon](https://ryobuild.com/hackathon) : tracks, calendrier et disponibilite des outils de recherche en lecture seule sur MCP et REST.
- [Site developpeur RYO-CHAN](https://dev.ryobuild.com/) : outils annonces et convention d'honnetete des donnees.
- L'URL MCP par defaut et l'authentification Bearer figurent aussi dans des exemples publics d'integration RYO; les schemas exacts des arguments restent a confirmer avec les informations d'acces fournies par les organisateurs.
