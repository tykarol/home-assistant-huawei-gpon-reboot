[![HACS Default][hacs_shield]][hacs]
[![GitHub Latest Release][releases_shield]][latest_release]
[![GitHub All Releases][downloads_total_shield]][releases]
[![Installations][installations_shield]][releases]
[![Revolut.Me][revolut_me_shield]][revolut_me]


[hacs_shield]: https://img.shields.io/static/v1.svg?label=HACS&message=Default&style=popout&color=green&labelColor=41bdf5&logo=HomeAssistantCommunityStore&logoColor=white
[hacs]: https://github.com/hacs/integration

[latest_release]: https://github.com/tykarol/home-assistant-huawei-gpon-reboot/releases/latest
[releases_shield]: https://img.shields.io/github/release/tykarol/home-assistant-huawei-gpon-reboot.svg?style=popout

[releases]: https://github.com/tykarol/home-assistant-huawei-gpon-reboot/releases
[downloads_total_shield]: https://img.shields.io/github/downloads/tykarol/home-assistant-huawei-gpon-reboot/total

[installations_shield]: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.huawei_gpon_reboot.total&style=popout&color=41bdf5&label=analytics

[revolut_me_shield]: https://img.shields.io/static/v1.svg?label=%20&message=Revolut&logo=revolut
[revolut_me]: https://revolut.me/karol9fi

# Huawei GPON Router Reboot for Home Assistant

A lightweight **Home Assistant Custom Component** that creates a dedicated button entity to remotely reboot **Huawei** home fiber gateway terminals (ONT/GPON) like the EchoLife series.

This integration runs 100% locally and serves as a reliable alternative to the built-in *Huawei LTE* integration, which does not support fiber/GPON gateway devices.

## 🚀 Compatibility
The integration automatically handles advanced Huawei WebUI security filters, including dynamic login CSRF challenges, hidden `GetRandCount.asp` BOM characters, and contextual operation tokens (`onttoken`). Tested successfully on:
- **Huawei EchoLife HG8245Q2** (Various ISP-branded firmware builds)
- Sibling models sharing the same WebUI layout (e.g., HG8245H, EG8145V5).

## 📦 Installation via HACS

You can add this repository directly into HACS to download it with one click:

To configure this integration go to: _Configuration_ -> _Integrations_ -> _Add integration_ -> _Huawei GPON Router Reboot_.

You can also use following [My Home Assistant](http://my.home-assistant.io/) link:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=huawei_gpon_reboot)

## 🤖 Example Automation for Periodic Reboot

To ensure network stability, you can use the newly created button to automate a weekly reboot cycle (e.g., every Wednesday at 4:00 AM):

```yaml
alias: "Scheduled Huawei GPON Fiber Reboot"
description: "Triggers a router reboot every Wednesday at 04:00 AM"
trigger:
  - platform: time
    at: "04:00:00"
condition:
  - platform: time
    weekday:
      - wed
action:
  - target:
      entity_id: button.huawei_gpon_reboot
    action: button.press
mode: single
```
