# Netz NÖ Smartmeter Integration for Home Assistant

## About

This repo contains a custom component for [Home Assistant](https://www.home-assistant.io) for exposing a sensor
providing information about a registered [Netz NÖ Smartmeter](https://www.netz-noe.at/smartmeter).

## Acknowledgments

This integration is based on the excellent [Wiener Netze Smartmeter](https://github.com/DarwinsBuddy/WienerNetzeSmartmeter) integration by [DarwinsBuddy](https://github.com/DarwinsBuddy) and contributors. We are grateful for their work which served as the foundation for this Netz NÖ adaptation.

Special thanks to the original contributors:
- [DarwinsBuddy](https://github.com/DarwinsBuddy) - Original Wiener Netze integration
- [platysma](https://github.com/platysma) - [vienna-smartmeter](https://github.com/platysma/vienna-smartmeter)
- [florianL21](https://github.com/florianL21/) - [vienna-smartmeter fork](https://github.com/florianL21/vienna-smartmeter/network)
- [reox](https://github.com/reox), [TheRealVira](https://github.com/TheRealVira), [tschoerk](https://github.com/tschoerk), [W-M-B](https://github.com/W-M-B)

## Installation

### Manual

Copy `<project-dir>/custom_components/netznoe` into `<home-assistant-root>/config/custom_components`

### HACS
1. Add this repository as a custom repository in HACS
2. Search for `Netz NÖ Smartmeter` or `netznoe` in HACS
3. Install
4. Restart Home Assistant
5. Configure the integration

## Configure

You can choose between UI configuration or manual (by adding your credentials to `configuration.yaml` and `secrets.yaml` resp.)
After successful configuration you can add sensors to your favourite dashboard, or even to your energy dashboard to track your total consumption.

### UI
Navigate to Settings > Devices & Services > Add Integration and search for "Netz NÖ".

### Manual
See [Example configuration files](example/configuration.yaml)