# A. O. Smith China AILink for Home Assistant

This workspace contains a first-pass Home Assistant custom integration for the
China A. O. Smith app (`AOSmartHome_release_2.3.1_signed.apk`).

APK strings show these likely cloud endpoints:

- `https://ailink-api.hotwater.com.cn`
- `/AiLinkService/user/login`
- `/AiLinkService/family/getFamilyList`
- `/AiLinkService/user/getFamilyIndex`
- `/AiLinkService/appDevice/getDeviceCurrInfo`
- `/AiLinkService/appDevice/getHomepageV2`
- `/AiLinkService/device/getDeviceList`
- `/AiLinkService/device/getUserDeviceList`
- `/AiLinkService/device/invokeMethod`

## Install

Copy `custom_components/aosmith_ailink` into the Home Assistant
`config/custom_components/` directory, restart Home Assistant, then add
`A. O. Smith AILink` from Settings > Devices & services.

Token mode is safest for early testing. Password login is scaffolded, but the
app may require SMS or Tencent captcha for some accounts. For control calls,
also enter `mobile`, `user_id`, `family_id`, and `device_id`. The app sends the
mobile number as `currUserMobile`, so token-only configurations still need it.

## Debugging

After setup, inspect the current and target water-temperature sensors. Cloud
payloads remain in memory for field mapping; no raw-state sensor is exposed.

Developer Tools can call:

```yaml
service: aosmith_ailink.invoke_method
data:
  device_id: "your-device-id"
  method: "SetTemperature"
  params:
    productType: "24"
    deviceType: "LL1GBQ24-E10"
    inputData:
      CommandValue: "44"
      CommandType: "0"
```

For the captured wall-hung boiler payload, `SetTemperature` with
`CommandType: "0"` controls domestic hot-water target temperature. The state
field is `waterTEMP`.

## Confirmed Services

The following captured app commands are integrated as Home Assistant services:

```yaml
service: aosmith_ailink.set_heating
data:
  enabled: true
```

`set_heating` sends `SetHeatingOnOff` with `CommandValue: "1"` when enabled,
and `CommandValue: "0"` when disabled.

```yaml
service: aosmith_ailink.start_one_key_quick_wash
```

`start_one_key_quick_wash` sends `SetCruiseOnOff`, `invokeChannel: "0"`,
`CommandValue: "1"`.

```yaml
service: aosmith_ailink.start_24h_quick_wash
```

`start_24h_quick_wash` sends `SetCruiseOnOff`, `invokeChannel: "0"`,
`CommandValue: "2"`.

## Switch Entities

The integration also exposes quick-wash modes as mutually-exclusive switches:

- `switch.aosmith_<device_id>_one_key_quick_wash`
- `switch.aosmith_<device_id>_quick_wash_24h`

Only one quick-wash mode can be active. Turning on one mode sends
`SetCruiseOnOff` with that mode's `CommandValue`, so the other mode is treated
as off after the next refresh. Turning either switch off sends
`SetCruiseOnOff` with `CommandValue: "0"`.

## 隐私与云端备份

本仓库包含完整 Home Assistant 集成源码与使用文档。账号、手机号、密码、
访问令牌、家庭 ID 和设备 ID 仅在 Home Assistant 配置界面填写，不写入代码。
Home Assistant 会在自己的配置目录保存这些配置，请保护好该目录及其备份。

`apk_analysis/` 是本地 APK 研究材料，包含反编译 DEX、字符串提取结果和证书库，
可能夹带第三方应用内置密钥，不纳入 GitHub。APK、抓包、日志、环境配置、
Home Assistant `.storage/` 和 `secrets.yaml` 也由 `.gitignore` 排除；原文件仍在本地。
整理后的公开协议信息和命令格式保留在本文与源码中。

运行日志只记录请求路径、HTTP 状态或完成事件，不输出完整云端响应。
分享诊断信息前仍需移除账号、令牌、设备标识、地址和网络信息。

本项目为非官方实验性集成，密码登录及云端接口兼容性仍需实机验证。
