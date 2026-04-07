# Pathloss Model
Based on ITU indoor model

## Pathloss
$L_{total} = 20log_{10}(f) + N_f log_{10}(d) + 20log_{10}(\frac{4 \pi}{c}) + \sum _{i}^{N_{walls}}L(wall_{i}) +L(d_o)$

### Power loss coefficients, N, 
for indoor transmission loss calculation. Parameterized by frequency
| Frequency Band (MHz) | Environment | N  |
|----------------------|-------------|----|
| 900                  | Office      | 20 |
| 2400                 | Office      | 20 |

# Misc Losses factor L(d_o)
Parameterized by frequency
| Frequency Band (MHz) | L(d₀) |
|----------------------|-------|
| 900                  | -5 (actually a gain)   |
| 2400                 | 0    |

## Received Signal Strength
$RSSI = G_{ANT_{TX}} + G_{ANT_{RX}} + P_{TX} + L_{total}$

