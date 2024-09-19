# Enable Full TX

This assumes you have a terminal open to the radio either via SSH or serial.

Serial speed: 115200

## Firmware Version 1.0.1
1. Edit xgradio.conf: `nano /etc/xgradio/xgradio.conf`
2. Set `fullband-tx` to `enable`

## xgradio.conf - Default
```
# XG Radio配置文件
# fullband-tx: 全频段发射开关
# +            enable
# +            disable

[mods]
fullband-tx=disable
```

## xgradio.conf - Updated
```
# XG Radio配置文件
# fullband-tx: 全频段发射开关
# +            enable
# +            disable

[mods]
fullband-tx=enable
```