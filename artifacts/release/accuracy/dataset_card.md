# EdgeDet-Z20 dataset card

## Source

BDD100K object-detection images and annotations are obtained from the official
Berkeley DeepDrive portal. Raw images and labels are not redistributed by this
repository. Users must review and follow the dataset's current terms.

## Mapping

| BDD100K label | EdgeDet label |
|---|---|
| `person`, `rider` | `person` |
| `bike` | `bicycle` |
| `motor` | `motorcycle` |
| `car` | `car` |
| `bus` | `bus` |
| `truck` | `truck` |

All other categories are ignored. Boxes are clipped to image bounds and
degenerate boxes are rejected.

## Splits

- 63,000 grouped samples from the official training set: training.
- 7,000 grouped samples from the official training set: development/validation.
- Official 10,000-image validation set: final held-out test.

Split manifests contain source identifiers and SHA-256 hashes. The converter
must reject overlap between manifests.

## Known limitations

The geographic and collection distribution can introduce bias. Small-object
performance at 160x160 is a primary risk. Final reporting must include class,
box-size, daytime/night, and weather breakdowns where metadata permits.

