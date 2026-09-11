# Étape 9-H2 — Wash trading / coordination : paires réciproques

Source : 43,3 M legs `quant` → 8,063,179 paires non-dirigées (volume total 1,533,629,414 $).

Marqueur utilisé : **paire réciproque** = des trades dans les deux sens entre deux wallets (`u→v` et `v→u`). `wash_usd = 2×min(vol_uv,vol_vu)` estime le volume qui fait un aller-retour (annulé) ; `recip` mesure la symétrie.

## Résultats

- Self-trades (maker==taker) : quasi nuls (2 edges) → pas de wash par auto-échange direct.
- Paires réciproques : **388,323 (4.82 % des paires)**, volume 625,736,182 $ = **40.80 %** du volume.
- Volume aller-retour estimé (wash_usd) : 237,076,762 $ = **15.46 %** du volume total.

### Paires wash-suspectes (seuils : réciproque + ≥10k$ + ≥20 trades)

**5,058 paires** représentant wash_usd = 139,325,553 $ (9.08 % du volume).

### Lecture pour H2

H2 postulait : *réseaux coordonnés (wash) < 5 % du volume mais 30 % des faux signaux*.
- **Self-trades : inexistants** → pas de wash par auto-échange direct (0 % du volume).
- **Volume aller-retour total** (proxy large, inclut market makers légitimes) : 15,5 %.
- **Paires wash-suspectes** (réciproque + ≥10k$ + ≥20 trades) : **9,1 %** du volume en aller-retour.
- Lecture prudente : le wash *avéré* (auto-échange) est **0 %** ; le wash *suspect* par
  réciprocité intense représente ~5-9 % selon le seuil — la borne <5 % de H2 n'est atteinte
  que pour les cas les plus extrêmes, et la réciprocité seule **ne permet pas** de trancher
  (elle capture aussi le market making légitime).

### Croisement avec la Smart Money (H1)
- 2 888 wallets uniques sont impliqués dans des paires wash-suspectes.
- Parmi les **99 wallets H1** (ROI>20 % & WR>65 %), seulement **4 (4 %)** apparaissent dans
  ces paires → la Smart Money *réelle* n'est **pas** concentrée sur le wash suspect.
- La seconde partie de H2 (« 30 % des faux signaux ») exigerait les scores prédits du
  classifieur (faux positifs) croisés au wash — piste laissée en prolongement.

### Conclusion H2
- Wash direct (auto-échange) : **inexistant**.
- Wash suspect (réciprocité intense) : ~5-9 % du volume, **non concentré sur la Smart Money**
  (4/99 wallets H1). H2 n'est que partiellement soutenue par ce proxy.
- Proxy sans connaissance de la **propriété des comptes** : une paire réciproque active peut être un market maker légitime qui quote les 2 côtés (réciprocité structurelle) — le wash réel exige 2 comptes d'une même entité.
- Seuls les legs touchant l'échantillon (10 k wallets) sont dans `net_edges` : les paires hors échantillon sont invisibles → bornes inférieures.
- Pas de vérité brute `orderfilled` pour arbitrer (limite du dataset).