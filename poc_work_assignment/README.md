# POC Work Assignment

Application Frappe autonome ciblant **v16.50.0**, sans ERPNext ni HRMS.
Les références employés sont des identifiants synthétiques, sans lien vers un DocType Employee.

## Structure et comportement

Les chemins ci-dessous sont relatifs à ce dossier, racine installable de
l’application. Le paquet Python est imbriqué dans `poc_work_assignment/`.

- `pyproject.toml` : paquet Python construit avec Flit, version statique 0.0.1
  pour conserver le `poc_work_assignment/__init__.py` original à l'identique.
- `poc_work_assignment/hooks.py`, `modules.txt`, `patches.txt` : métadonnées Frappe.
- `poc_work_assignment/poc_work_assignment/doctype/poc_work_assignment/` :
  DocType standard, contrôleur et tests d'intégration.
- `poc_work_assignment/validation.py` et `../tests/test_validation.py` :
  règles de validation et tests unitaires indépendants de Frappe.

Le DocType comporte trois champs obligatoires : `employee_ref` (Data),
`assignment_date` (Date), `assignment_type` (Select : Office, Sales, Training).
`location` (Data) et `notes` (Small Text) sont facultatifs.
Les permissions CRUD sont accordées au rôle standard **System Manager**.

Le contrôleur vérifie les champs obligatoires, les types autorisés et les doublons
sur `(employee_ref, assignment_date, assignment_type)`, en excluant le document
courant lors d'une modification. Frappe assure aussi la validation native des
champs et des dates. Le hook de synchronisation `on_doctype_update` ajoute une
contrainte unique composite pour protéger également les écritures concurrentes.
Des types distincts sont autorisés pour un employé à une même date.
L'égalité des identifiants suit la collation de la base Frappe : sur MariaDB,
elle peut notamment être insensible à la casse.

## Vérifications locales exécutées

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" python -m unittest discover -s ../tests -v
```

Résultats de la vérification du packaging :

- 3 tests unitaires réussis avant et après déplacement, puis depuis `/tmp`
  après installation éditable, sans `PYTHONPATH`.
- Construction Flit du sdist, puis de la wheel depuis ce sdist : réussie.
  Archives produites dans `/tmp/poc-packaging-dist/`.
- Présence dans la wheel des fichiers Python, du JSON du DocType, de
  `modules.txt`, `patches.txt` et de la licence ; README et pyproject présents
  dans le sdist. Aucune dépendance `Requires-Dist` dans la wheel.
- Analyse AST Python, lecture TOML/JSON, contrôle des espaces de fin de ligne
  et `git diff --check` : réussis.
- Lors du déplacement pour le packaging, tous les fichiers originaux du paquet
  ont été conservés octet par octet, y compris
  le DocType, les règles métier et les tests d’intégration.
- Ruff : 3 écarts préexistants dans les tests (`I001` sur les imports du test
  d’intégration, deux `SIM117` dans les tests unitaires). Aucun correctif de
  style appliqué pour préserver les tests.

Flit, build et Ruff ont été installés uniquement dans un environnement jetable
`/tmp/poc-packaging-check-env`, hors stack RH. Python disponible : 3.13.15.
Le test d’installation éditable a utilisé `--no-deps --no-build-isolation
--ignore-requires-python` uniquement pour vérifier le packaging avec cet
interpréteur. Il ne valide pas l’exécution sous Python 3.14, exigé par le
package, ni l’installation Frappe. Ne pas contourner cette exigence dans le bench.

## Packaging et installation

`pyproject.toml`, `README.md` et `license.txt` sont réunis dans ce dossier.
Flit embarque le paquet Python, les métadonnées Frappe, le JSON du DocType
et la licence. Aucune dépendance Python ERPNext ou HRMS n’est déclarée ;
Frappe est fourni par le bench (`>=16.50.0,<17.0.0`).

Le dépôt contient l’application dans un sous-dossier : ne pas utiliser
`bench get-app` sur la racine du dépôt. Monter ou copier **ce dossier complet**
dans `<bench-isole>/apps/poc_work_assignment`. Depuis ce bench, avec Python
3.14 et Frappe v16.50.0 déjà disponibles :

```sh
./env/bin/python -m pip install --no-deps -e apps/poc_work_assignment
```

Vérifier que `poc_work_assignment` figure une seule fois dans `sites/apps.txt`,
puis, sur un site de test isolé uniquement :

```sh
bench --site <site-de-test-isole> install-app poc_work_assignment
bench --site <site-de-test-isole> run-tests --app poc_work_assignment
```

Résultats confirmés par l’utilisateur sur le VPS isolé, site `integration-poc.local`
(Frappe v16.50.0, Python 3.14.8, MariaDB 11.8) :

- Installation de l’application : réussie.
- Tests unitaires : **3/3 PASS**.
- Tests d’intégration Frappe : **10/10 PASS**.
- Comportement `assignment_type=None` → `Office` confirmé : à l’insertion,
  Frappe applique la première option du Select avant la validation. Le test des
  champs obligatoires utilise `""`, qui reste vide et est rejeté.

Ces résultats d’intégration proviennent du VPS ; les tests n’ont pas été
réexécutés dans ce workspace lors de cette mise à jour documentaire.
Ne pas utiliser `prototype-rh.dgid.pro`.

Les tests d'intégration couvrent la persistance sans champs facultatifs, le refus
d'un doublon, les trois types le même jour, un autre employé ou une autre date,
les champs obligatoires, un type invalide, la modification du document courant,
une modification créant un doublon, la valeur par défaut du Select et la contrainte
SQL en contournant le précontrôle du contrôleur. Ce dernier test vérifie la
contrainte, pas une course réelle entre deux transactions.

## Références consultées

Les skills locaux `frappe-app-dev` et `code-style` ont été lus. Les fichiers
`references/*.md` annoncés par le premier sont absents localement ; la référence
`existing-app.md` a été retrouvée dans `/projects/frappe-skills-poc/.agents/skills/`. La structure a été créée
directement à la demande de l'utilisateur, sans migration ni création de site.
Context7 a été consulté avec `/frappe/frappe/__branch__version-16` pour les
conventions d'application, le hook de synchronisation et `IntegrationTestCase`.
Son index ne proposait pas le tag v16.50.0 ; les points suivants ont également
été vérifiés dans les sources officielles figées :

- [Python et backend de build](https://github.com/frappe/frappe/blob/v16.50.0/pyproject.toml)
- [Hook de synchronisation du DocType](https://github.com/frappe/frappe/blob/v16.50.0/frappe/core/doctype/doctype/doctype.py)
- [Contrainte unique MariaDB](https://github.com/frappe/frappe/blob/v16.50.0/frappe/database/mariadb/database.py)
- [Exports de tests](https://github.com/frappe/frappe/blob/v16.50.0/frappe/tests/__init__.py)
- [Exception de contrainte unique](https://github.com/frappe/frappe/blob/v16.50.0/frappe/model/base_document.py)

- [Structure générée pour une application v16.50.0](https://github.com/frappe/frappe/blob/v16.50.0/frappe/utils/boilerplate.py)
