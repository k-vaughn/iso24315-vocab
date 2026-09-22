[Home](../index.md) · [METR Architectural Terms](groups/METR Architectural Terms.md) · [METR Role Terms](patterns/METR Role Terms.md) · stored data provider

# stored data provider

[supporting data provider](supporting data provider.md) that is built into the user's [material entity](https://isotc204.org/iso14812/terms/material entity/) hosting the [receiver](receiver.md) and provides [supporting data](supporting data.md) that has been previously configured within the device

<object type="image/svg+xml" data="../../diagrams/stored data provider.dot.svg">
    <img alt="stored data provider Diagram" src="../../diagrams/stored data provider.dot.png" /> <!-- Fallback for non-SVG browsers -->
</object>

Clause: 3.3.1.26

EXAMPLE: Data store that provides configured information such as vehicle characteristics, such as engine size, fuel type, vehicle width, length, and height, etc.

Note 1 to entry: Stored data can change, but changes tend to be infrequent. Example changes can include a parking permit being added, a cargo carrier being attached that changes the vehicle's effective dimensions, or snow chains being installed on tires.

## Relationships for stored data provider

| Property | Constraint |
| --- | --- |
| subClassOf | supportingDataProvider |


---

[Comment on this page](https://github.com/ISO-TC204/iso24315-vocab/issues/new?template=page-feedback.yml&title=%5BPage+feedback%5D+stored+data+provider&page-title=stored+data+provider&page-path=terms%2Fstored+data+provider.md)

