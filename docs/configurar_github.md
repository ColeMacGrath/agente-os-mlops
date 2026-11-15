# Configurar el repositorio en GitHub · paso a paso

Guía para subir el repositorio y dejar funcionando los tres workflows: **CI** (pipeline MLOps), **CD** (despliegue GitOps) y **monitoreo semanal**. Los pasos 1 a 8 son obligatorios; el 9 (Google Cloud) es opcional: sin él, el CD usa el entorno simulado.

> **Estado:** en este repositorio ya se aplicaron los pasos 1 a 8: DVC con Git, usuario `colemacgrath` en las imágenes, commits por etapas, permisos de Actions, entornos `staging` y `produccion`, protección de `main` y el ciclo completo CI → CD → producción con su evidencia en `docs/evidencias/capturas/github_*.png`. El nombre de la imagen se calcula en minúsculas dentro del CI, porque `ghcr.io` no acepta mayúsculas.

---

## 1. Antes de `git init`: preparar DVC

DVC se inicializó sin Git (`no_scm`) porque el repositorio aún no existía. Abre `.dvc/config` y **borra** estas dos líneas:

```ini
[core]
    no_scm = True
```

El archivo puede quedar vacío. Con esto, DVC usará Git normalmente.

## 2. Reemplazar `OWNER` por tu usuario de GitHub

El marcador aparece en 4 lugares (imagen de los releases, etiqueta del Dockerfile y la prueba de rollback). Desde la carpeta `agente-os-mlops`:

```bash
USUARIO=tu-usuario-de-github
sed -i '' "s/OWNER/$USUARIO/g" Dockerfile deploy/entornos/*/release.yaml gitops/analisis_canary.py
grep -rn "OWNER" Dockerfile deploy gitops    # no debe imprimir nada
```

> El nombre de usuario debe ir en minúsculas en la URL de `ghcr.io`.

## 3. Inicializar Git y hacer commits con historia

Conviene subir el trabajo en varios commits con sentido, en lugar de uno solo. Así el historial sirve de evidencia del proceso:

```bash
git init -b main
git add .gitignore .dvcignore .dvc pyproject.toml requirements*.txt Makefile README.md CHANGELOG.md
git commit -m "chore: estructura del proyecto y dependencias"

git add src data params.yaml
git commit -m "feat: servicio, barreras v3, router y conjuntos de evaluación"

git add pipelines dvc.yaml dvc.lock models/manifest.json models/release.json reports
git commit -m "feat: pipeline DVC con validación de datos, entrenamiento, evaluación y compuerta"

git add tests
git commit -m "test: pruebas unitarias, de datos, de modelo y de API"

git add Dockerfile .dockerignore deploy gitops .github
git commit -m "ci: workflows de CI/CD, manifiestos GitOps y análisis de canary"

git add operacion docs
git commit -m "docs: operación simulada, auditoría, ADR, bitácora y evidencias"

git status        # debe decir "nothing to commit"
```

`git status` no debe listar `mlflow.db`, `mlruns/`, `data/procesados/` ni `models/riesgo/`: los ignora `.gitignore` porque su versión está en `dvc.lock`.

## 4. Crear el repositorio en GitHub y subirlo

1. En GitHub: **New repository** → nombre `agente-os-mlops` → *Private* o *Public* → **sin** README ni .gitignore (ya existen).
2. Sube el repositorio:

```bash
git remote add origin https://github.com/$USUARIO/agente-os-mlops.git
git push -u origin main
```

## 5. Permisos de GitHub Actions

En el repositorio: **Settings → Actions → General**

- *Actions permissions*: **Allow all actions and reusable workflows**.
- *Workflow permissions*: **Read and write permissions**.
- Marca **Allow GitHub Actions to create and approve pull requests**. Sin esto falla el paso que abre el PR GitOps.

Guarda con **Save**.

## 6. Entornos de despliegue

**Settings → Environments → New environment**:

1. `staging`: sin reglas.
2. `produccion`: activa **Required reviewers** y agrégate. Así el despliegue a producción espera una aprobación manual, como indica el plan de gobernanza.

## 7. Protección de la rama `main` (recomendado)

**Settings → Branches → Add branch ruleset** (o *Add rule*) para `main`:

- **Require a pull request before merging**.
- **Require status checks to pass**: agrega `Lint y pruebas unitarias y de datos`, `Pipeline de datos y modelos (DVC + compuertas)` e `Imagen y prueba de humo`. Aparecen después de la primera ejecución del CI.

## 8. Primera ejecución y evidencias

El `git push` del paso 4 dispara el **CI**. Ve a la pestaña **Actions**:

1. **CI · pipeline MLOps**: espera a que terminen los 4 jobs (~6–8 min). Toma capturas de:
   - el grafo de jobs en verde;
   - el **Summary**, con las métricas de `dvc metrics show` y la tabla de la compuerta por componente;
   - la sección **Artifacts** (`modelos-y-reportes`).
2. **Pull requests**: el job `gitops-staging` abre un PR `deploy(staging): r-<sha>`. Captura el diff de `release.yaml` y **haz merge**.
3. El merge dispara **CD · despliegue GitOps**. Sin Google Cloud corre el reconciliador y el análisis de canary en el runner. Captura el log del paso *Entorno simulado* y el PR de promoción a producción que se abre al final.
4. **Monitoreo semanal**: córrelo a mano desde **Actions → Monitoreo semanal → Run workflow**. Como el clasificador de inyección está en sombra, abrirá un **issue** con el componente fuera de compuerta. Captura el issue.
5. **Packages**: en tu perfil aparecerá `agente-os-cloud`. Ábrelo y captura las etiquetas de la imagen.

## 9. (Opcional) Despliegue real en Google Cloud Run

Solo si quieres que el CD despliegue en Cloud Run en lugar del entorno simulado.

```bash
PROYECTO=tu-proyecto-gcp
gcloud services enable run.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com --project $PROYECTO
gcloud iam service-accounts create agente-os-deploy --project $PROYECTO
gcloud iam service-accounts create agente-os-run --project $PROYECTO
for rol in roles/run.admin roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding $PROYECTO --member "serviceAccount:agente-os-deploy@$PROYECTO.iam.gserviceaccount.com" --role $rol
done
gcloud iam workload-identity-pools create github --location global --project $PROYECTO
gcloud iam workload-identity-pools providers create-oidc github --location global --workload-identity-pool github \
  --issuer-uri https://token.actions.githubusercontent.com \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition "assertion.repository=='$USUARIO/agente-os-mlops'" --project $PROYECTO
NUM=$(gcloud projects describe $PROYECTO --format 'value(projectNumber)')
gcloud iam service-accounts add-iam-policy-binding agente-os-deploy@$PROYECTO.iam.gserviceaccount.com --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$NUM/locations/global/workloadIdentityPools/github/attribute.repository/$USUARIO/agente-os-mlops"
printf '%s' "TU_LLAVE_DE_ANTHROPIC" | gcloud secrets create anthropic-api-key --data-file=- --project $PROYECTO
printf '%s' "$(openssl rand -hex 24)" | gcloud secrets create agent-token --data-file=- --project $PROYECTO
```

En GitHub, en **Settings → Secrets and variables → Actions → Variables**, crea:

| Variable | Valor |
|---|---|
| `GCP_PROJECT` | tu proyecto |
| `GCP_WIF_PROVIDER` | `projects/<NUM>/locations/global/workloadIdentityPools/github/providers/github` |
| `GCP_DEPLOY_SA` | `agente-os-deploy@<proyecto>.iam.gserviceaccount.com` |

Con `GCP_PROJECT` definida, el CD usa `gitops/desplegar_cloudrun.py` (dos regiones con reparto de tráfico) en lugar del entorno simulado. Ten en cuenta que esto genera costo en Google Cloud y en la API de Claude.

## Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `dvc repro` falla en el CI con un error de SCM | No se quitó `no_scm` (paso 1). Bórralo, haz commit y push. |
| *GitHub Actions is not permitted to create pull requests* | Falta la casilla del paso 5. |
| `denied: permission_denied` al publicar la imagen | Revisa el paso 5 (*Read and write*). Si el paquete ya existía, en **Package settings → Manage Actions access** agrega el repositorio con rol *Write*. |
| La prueba de humo no encuentra modelos | El job `contenedor` descarga el artefacto `modelos-y-reportes` del job `modelo`; revisa que este terminó en verde. |
| El monitoreo abre un issue cada semana | Es lo esperado mientras la inyección esté en sombra (ADR-0002). Se cierra cuando un nuevo conjunto (F5) permita promoverla. |
