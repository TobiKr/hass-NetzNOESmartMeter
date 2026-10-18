# NetzNÖ Smartmeter Integration for Home Assistant
![Hassfest](https://github.com/TobiKr/hass-NetzNOESmartMeter/actions/workflows/hassfest.yml/badge.svg)
![Validate](https://github.com/TobiKr/hass-NetzNOESmartMeter/actions/workflows/validate.yml/badge.svg)
![Release](https://github.com/TobiKr/hass-NetzNOESmartMeter/actions/workflows/release.yml/badge.svg)

## About

This repo contains a custom component for [Home Assistant](https://www.home-assistant.io) for exposing a sensor
providing information about a registered [NetzNÖ Smartmeter](https://www.netz-noe.at/smartmeter).

The integration syncs all consumption data in Home Assistant, which allows a hourly view on consumption data in Home Assistant:
![Screenshot of the energy dashboard, showing hourly consumption measured by a NetzNÖ SmartMeter](/docs/netznoe-energyusage.png)

## Acknowledgments

This integration is based on the excellent [Wiener Netze Smartmeter](https://github.com/DarwinsBuddy/WienerNetzeSmartmeter) integration by [DarwinsBuddy](https://github.com/DarwinsBuddy) and contributors. We are grateful for their work which served as the foundation for this Netz NÖ adaptation.

## Installation

### Manual

Copy `<project-dir>/custom_components/netznoe` into `<home-assistant-root>/config/custom_components`

### HACS
1. Add this repository as a custom repository in HACS
2. Search for `NetzNÖ Smartmeter` or `netznoe` in HACS
3. Install
4. Restart Home Assistant
5. Configure the integration

## Configure

You can choose between UI configuration or manual (by adding your credentials to `configuration.yaml` and `secrets.yaml` resp.)
After successful configuration you can add sensors to your favourite dashboard, or even to your energy dashboard to track your total consumption.

### UI
1. Navigate to Settings > Devices & Services > Add Integration
2. Search for "NetzNÖ" and add the integration
3. Enter your NetzNÖ SmartMeter Portal credentials and confirm
4. Adding the SmartMeter can take a couple of minutes as it syncs all existing data

### Manual
See [Example configuration files](example/configuration.yaml)

### Options
After setup, the following options can be changed via Settings > Devices & Services > NetzNÖ Smartmeter > Configure:

- **Import estimated values** (default: off): Netz NÖ sometimes only provides estimated values (quality L3) for a day. By default these are skipped, leaving a gap until measured values are available. When enabled, the estimates are imported instead and replaced once measured values arrive within the re-import window.
- **Days to re-import** (default: 7): On every update, this many past days are fetched again and rewritten. This fills gaps from values that arrived late and picks up corrections. Set to 0 to only import data newer than the last imported value.

## Requirements

Home Assistant 2025.11 or newer.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
