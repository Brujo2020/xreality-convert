# Ollama Image Studio

Application native macOS pour générer, en local, **des images**, **des modèles 3D (STL)** à partir d'un prompt, et **des modèles 3D à partir d'une photo** — sans passer par le terminal. Construite avec Electron + React, pensée pour Apple Silicon.

![Ollama Image Studio — génération d'image](docs/screenshot.png)

![Ollama Image Studio — module STL 3D](docs/screenshot-stl.png)

## Fonctionnalités

L'app a **trois modes**, sélectionnables en haut du panneau :

### 🖼️ Mode Image
- Génération d'images via le modèle `x/z-image-turbo` (affiché **en rouge** avec la commande d'installation s'il n'est pas présent).
- Paramètres : largeur / hauteur (512–2048), nombre d'étapes, *seed* (+ bouton aléatoire 🎲).
- Sauvegarde dans `~/Pictures/OllamaImageStudio/`.

### 🧊 Mode STL 3D
- Choix libre du modèle de **code** parmi ceux installés localement.
- Pipeline : *prompt → le modèle écrit du code [JSCAD](https://github.com/jscad/OpenJSCAD.org) → compilation en STL dans l'app → rendu 3D*.
- **Visualiseur 3D interactif** (rotation à la souris, zoom à la molette) via Three.js.
- Bouton **« View code »** pour inspecter le code JSCAD généré.
- Sauvegarde du `.stl` dans `~/Documents/OllamaImageStudio/`.
- Robustesse : *system prompt* détaillé + couche de compatibilité tolérante + **auto-réparation** (si le code échoue, l'erreur est renvoyée au modèle pour correction, jusqu'à 3 essais).

### 🗿 Mode Image → 3D (Hunyuan3D, avancé)
- Transforme **une image** (photo ou image générée) en **modèle 3D** via [Hunyuan3D 2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) tournant **en local sur Apple Silicon** (MLX).
- Choix du nombre d'étapes, **taille STL configurable (mm)** pour l'impression, et **texture couleur (PBR)** optionnelle.
- Visualiseur 3D, export **GLB** (avec couleur) et **STL** (pour l'impression 3D, mis à l'échelle).
- ⚙️ **Nécessite un serveur local séparé** (voir [Mode Image → 3D : installation](#mode-image--3d--installation-serveur-local)). Sans lui, le mode affiche « serveur off ».
- ⏱️ ~9 min pour la forme, ~9 min de plus avec la texture (sur M2 Pro).

### Commun à tous les modes
- ✅ Vérification automatique de la connexion à Ollama + détection des modèles.
- 🗂️ Galerie des 20 dernières générations (clic = recharge les paramètres). Métadonnées persistées sur disque.
- ⏹️ Génération annulable à tout moment.
- 📋 Copier le prompt, 📂 révéler le fichier dans le Finder.
- 🌙 Thème sombre, barre de titre macOS native.

## Prérequis

- macOS (Apple Silicon recommandé)
- [Ollama](https://ollama.com) installé et lancé : `ollama serve`
- **Pour les images** : `ollama pull x/z-image-turbo`
- **Pour le STL** : un modèle de code. Recommandé pour la meilleure qualité :
  un modèle *cloud* comme `gpt-oss:120b-cloud` ; en local, `qwen2.5-coder` fonctionne aussi.
- Node.js 18+ (pour compiler depuis les sources)

> **Note** : la génération d'image via `/api/generate` d'Ollama est un point d'API expérimental.
> Pour le STL, la qualité dépend fortement du modèle de code choisi : les modèles plus
> puissants produisent des formes nettement plus détaillées.

## Lancer depuis les sources

```bash
git clone https://github.com/koua29/ollama-image-studio.git
cd ollama-image-studio
npm install
npm run dev      # lance Vite + Electron en mode développement
```

## Construire une app distribuable

```bash
npm run build    # produit un .app et un .dmg dans release/
```

Glissez ensuite **Ollama Image Studio.app** dans votre dossier `/Applications`, ou ouvrez le `.dmg`.

## Mode Image → 3D : installation (serveur local)

Le mode **Img→3D** s'appuie sur Hunyuan3D 2.1 (port MLX), qui tourne dans un **petit serveur Python séparé** (l'app le contacte sur `http://127.0.0.1:8765`). C'est une fonctionnalité **avancée**, distincte du cœur de l'app.

Prérequis : Mac Apple Silicon (32 Go recommandés), Python 3.11, ~14 Go de poids de modèle.

1. Récupère le pipeline MLX et les poids ([dgrauet/Hunyuan3D-2.1-mlx](https://github.com/dgrauet/Hunyuan3D-2.1-mlx), poids sur [Hugging Face](https://huggingface.co/dgrauet/hunyuan3d-2.1-mlx)).
2. Crée un venv et installe les dépendances (`requirements-mlx.txt`).
3. Lance le serveur — un script double-cliquable est fourni :
   ```
   ./start-3d-server.command
   ```
   Garde la fenêtre ouverte ; le badge passe à « serveur OK » dans l'app.

> Sans ce serveur, les modes **Image** et **STL** fonctionnent normalement ; seul **Img→3D** est désactivé.

## Architecture

```
ollama-image-studio/
├── electron/
│   ├── main.js       # processus principal : IPC, appels HTTP Ollama, pipeline JSCAD→STL
│   └── preload.js    # contextBridge — expose une API sûre window.ollama
└── src/
    ├── App.jsx       # état de l'application
    └── components/   # Header, PromptPanel, ImageViewer, StlViewer, Gallery
```

**Choix techniques**

- Tous les appels HTTP à Ollama se font dans le **processus principal** (module `http` de Node, zéro dépendance) — pas de problème de CORS et le *renderer* reste isolé.
- Le code JSCAD généré par le modèle est exécuté dans un **bac à sable `vm` verrouillé** (pas d'accès fichier/réseau, exécution bornée dans le temps), puis sérialisé en STL.
- Sécurité : `nodeIntegration: false`, `contextIsolation: true`, `sandbox: true`, plus une Content-Security-Policy stricte.

## ☕ Offrez-moi un café

Cette application est gratuite et open source. Si elle vous est utile, vous pouvez me remercier
en m'offrant un café — il suffit de scanner ce QR code PayPal. Merci beaucoup ! 🙏

<p align="center">
  <img src="docs/paypal-qr.png" alt="QR code PayPal pour offrir un café" width="220" />
</p>

## Licence

[MIT](LICENSE) © 2026 Arnaud Soulas
