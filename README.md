# OpenHands Sandbox — POC Work Assignment

L’application Frappe autonome se trouve dans [`poc_work_assignment/`](poc_work_assignment/README.md).
Ce sous-répertoire est la racine installable à monter dans `apps/poc_work_assignment`
du bench isolé. Il contient le `pyproject.toml`, le README et la licence MIT.
La racine du dépôt n’est pas un paquet Python installable.

Les tests unitaires restent dans `tests/`. Depuis la racine du dépôt :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/poc_work_assignment" python -m unittest discover -s tests -v
```

Voir le README de l’application pour les vérifications et les étapes Frappe restantes.
