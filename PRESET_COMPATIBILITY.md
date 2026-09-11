# Preset compatibility fixes

This branch adds two configuration/API fixes to upstream v0.66.1. It does not change PID calculations, adaptive learning, heater timing, or control output.

- Accept and load `sleep_temp` in the `adaptive_climate` domain configuration, alongside the other preset temperatures.
- Register the public `adaptive_climate.set_preset_temp` entity service, using the existing temperature-manager implementation. Supports away, eco, boost, comfort, home, sleep and activity temperatures independently or together.

Example domain setting (not a climate platform setting):

```yaml
adaptive_climate:
  sleep_temp: 20.2
  preset_sync_mode: sync
```

Example action for an existing temperature helper:

```yaml
action: adaptive_climate.set_preset_temp
target:
  entity_id: climate.thermostat
data:
  sleep_temp: "{{ states('input_number.sleep') | float }}"
```

The example entity and helper must already exist. This fork does not migrate entities, change schedules, or replace an existing thermostat automatically. Dynamic preset updates use upstream behavior; they do not introduce new preset persistence or heating behavior.

Validation: 159 focused configuration, setup, manager and preset regression tests passed locally. These tests mock Home Assistant; live migration and restart validation remain separate steps.
