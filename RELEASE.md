# Cypher v1.0.0 Release Checklist

## Stability

- [ ] CLI frozen
- [ ] GUI polished
- [ ] encode works
- [ ] bundle works
- [ ] decode works
- [ ] inspect works
- [ ] benchmark works
- [ ] waveform preview works
- [ ] macOS app builds
- [ ] macOS app opens
- [ ] README final
- [ ] no major known bugs

## Public repo readiness

- [ ] no private keys
- [ ] no local payloads
- [ ] no .DS_Store
- [ ] no secret material
- [ ] no personal test data
- [ ] license present
- [ ] assets present
- [ ] install instructions tested

## Release commands

```bash
make release-check
make clean-app
make app
git status
git tag -a v1.0.0 -m "release: Cypher v1.0.0 stable"
git push origin main
git push origin v1.0.0

