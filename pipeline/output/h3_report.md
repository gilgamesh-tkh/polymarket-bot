# Étape 9-H3 — Anomalies de volume → mouvements de prix (longshots)

Marchés : résolus binaires 2025, volume 1-50k$ (117,705). Heures-marchés : 2,195,505. Anomalies détectées : 193,561.

### Définitions
- **Anomalie** : volume horaire ≥ 5× médiane des 24 h précédentes ET ≥ 200 $.
- **Longshot** : prix moyen horaire < 0,05 ou > 0,95 (prob. implicite < 5 %).
- **Mouvement** : |Δprix| maximal dans les 24 rangs horaires suivants > 0,15.

### Résultats (heures longshot)

| Groupe | n | P(Δ>15% en 24h) | médiane \|Δ\| |
|---|---|---|---|
| longshot (tous) | 950,977 | **5.4 %** | 0.011 |
| sans anomalie (baseline) | 879,031 | **5.4 %** | 0.011 |
| **avec anomalie** | 71,821 | **5.7 %** | 0.020 |

Test t de Welch (|Δ| anomalie vs baseline) : t=5.79, p=7.14e-09

### Lecture pour H3
H3 : *une anomalie de volume soudaine sur un marché longshot prédit un mouvement > 15 % en 24 h*.
- Le test est **statistiquement significatif** (p ≈ 7×10⁻⁹) mais **faible en pratique** :
  P(Δ>15 %) passe de 5,4 % (baseline) à 5,7 % seulement (+0,3 pt).
- La **médiane |Δ| double** (0,011 → 0,020) : l'anomalie précède des mouvements
  *légèrement plus grands*, mais rarement > 15 %.

### Analyse de sensibilité (seuil d'anomalie ×3 à ×20)
| seuil | n anomalie | P(Δ>15 %) anomalie | P(Δ>15 %) baseline |
|---|---|---|---|
| ×3 | 75 769 | 5,72 % | 5,37 % |
| ×5 | 71 821 | 5,72 % | 5,37 % |
| ×10 | 63 661 | 5,60 % | 5,38 % |
| ×20 | 53 226 | 5,49 % | 5,38 % |

Le résultat est **robuste au seuil** mais l'effet reste ~0,2-0,4 pt : augmenter la
sévérité ne concentre pas davantage le signal → le volume ne précède pas de grands
mouvements sur ces longshots.

### Conclusion H3
**Non soutenue quantitativement.** Les anomalies de volume sur marchés longshots à faible
liquidité précèdent des mouvements de prix légèrement plus amples que la baseline
(statistiquement détectable), mais la probabilité d'un mouvement > 15 % en 24 h reste
~5,7 % — très loin d'un signal prédictif exploitable. Interprétation probable : sur ces
marchés, le volume *suit* le prix (momentum/réaction) plutôt qu'il ne le *précède*.

### Limites
- Heures sans trade absentes de la série → '24 rangs' ≈ 24 h effectives, pas calendaires.
- Le prix est en perspective YES ; les deux extrêmes (<0,05 ou >0,95) couvrent les deux côtés, mais le mouvement est mesuré sur le prix YES uniquement.
- Seuils (×5, 200 $, 0,15) arbitraires mais documentés ; une analyse de sensibilité est possible.