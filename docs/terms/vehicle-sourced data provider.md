[Home](../index.md) · [METR Architectural Terms](groups/METR Architectural Terms.md) · [METR Role Terms](patterns/METR Role Terms.md) · vehicle-sourced data provider

# vehicle-sourced data provider

[supporting data provider](supporting data provider.md) that provides [vehicle-sourced data](vehicle-sourced data.md)

<object type="image/svg+xml" data="../../diagrams/vehicle-sourced data provider.dot.svg">
    <img alt="vehicle-sourced data provider Diagram" src="../../diagrams/vehicle-sourced data provider.dot.png" /> <!-- Fallback for non-SVG browsers -->
</object>

Clause: 3.3.1.31

EXAMPLE: GNSS positioning data (i.e., GNSS positioning data is determined by an on-board algorithm that analyses multiple GNSS signals to produce an estimate of a geographic position).

Note 1 to entry: In-vehicle data providers can produce [supporting data](supporting data.md) that is derived from external data sources, for example by using sensors, clocks, GNSS receivers, and/or other devices with its own algorithms.

Note 2 to entry: The "user device" is nominally a vehicle, but can be a smartphone if it hosts the METR [receiver](receiver.md), e.g., in the case of a pedestrian.

## Relationships for vehicle-sourced data provider

| Property | Constraint |
| --- | --- |
| subClassOf | supportingDataProvider |


---

[Comment on this page](https://github.com/ISO-TC204/iso24315-vocab/issues/new?template=page-feedback.yml&title=%5BPage+feedback%5D+vehicle-sourced+data+provider&page-title=vehicle-sourced+data+provider&page-path=terms%2Fvehicle-sourced+data+provider.md)

