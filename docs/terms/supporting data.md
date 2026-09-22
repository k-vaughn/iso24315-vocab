[Home](../index.md) · [Data Terms](groups/Data Terms.md) · [General Data Terms](patterns/General Data Terms.md) · supporting data

# supporting data

data provided by a source other than the [METR system of systems](METR system of systems.md) that can impact the interpretation of a [rule](rule.md)

<object type="image/svg+xml" data="../../diagrams/supporting data.dot.svg">
    <img alt="supporting data Diagram" src="../../diagrams/supporting data.dot.png" /> <!-- Fallback for non-SVG browsers -->
</object>

Clause: 3.2.1.17

Note 1 to entry: Derived from SP-54,SP-75,SP-133.

Note 2 to entry: Supporting data can be categorized into [vehicle-sourced](vehicle-sourced data.md), [infrastructure-sourced](infrastructure-sourced data.md), [crowd-sourced](crowd-sourced data.md), and [user-sourced](user-sourced data.md) data.

Note 3 to entry: Supporting data often changes more frequently than the [freshness periods](freshness period.md) defined for [METR information](METR information.md).

Note 4 to entry: Supporting data can affect the applicability of a rule (e.g., the current time affects the applicability of a time-based rule), can provide parameters for a rule (e.g. the current speed limit for a variable speed limit rule), or provide additive, redundant, or inconsistent information (e.g., an on-board system can detect road signs that the interpreter needs to consider in addition to the METR information).

## Specializations of supporting data

| Class | Description |
| --- | --- |
| [crowd-sourced data](crowd-sourced data.md) | [supporting data](supporting data.md) from multiple external sources that are not signed by any [jurisdictional entity](jurisdictional entity.md) associated with the current location |
| [infrastructure-sourced data](infrastructure-sourced data.md) | [supporting data](supporting data.md) from an external source that has a fixed or portable location, including Internet servers |
| [jurisdiction-sourced data](jurisdiction-sourced data.md) | [supporting data](supporting data.md) from an external source and that is signed by a [jurisdictional entity](jurisdictional entity.md) associated with the current location |
| [peer-sourced data](peer-sourced data.md) | [supporting data](supporting data.md) from an external source that is designed to operate when mobile |
| [user-sourced data](user-sourced data.md) | [supporting data](supporting data.md) provided by the human user of the system |
| [vehicle-sourced data](vehicle-sourced data.md) | [supporting data](supporting data.md) provided by built-in equipment |


---

[Comment on this page](https://github.com/ISO-TC204/iso24315-vocab/issues/new?template=page-feedback.yml&title=%5BPage+feedback%5D+supporting+data&page-title=supporting+data&page-path=terms%2Fsupporting+data.md)

