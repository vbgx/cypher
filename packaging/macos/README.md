# macOS packaging

Build native app bundle:

```bash
make app

Output:

dist/Cypher.app

Open:

open dist/Cypher.app

Clean packaging artifacts:

make clean-app

Notes:

Uses PyInstaller.
Bundles GUI entrypoint.
Includes src/sounds_library when present.
Includes assets when present.
App is unsigned for now.
