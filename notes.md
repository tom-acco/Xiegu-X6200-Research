# Wifi
Issues connecting to Wifi through UI can be resolved by using CLI.

**Note:** Ensure Wifi is switched on from the radio UI first

## List access points
```bash
nmcli device wifi
```

## Connect to an access point

```bash
nmcli device wifi connect '<AP NAME>' password '<PASSWORD>'
```

## AP Mode?
Doesn't seem to work. Errors when bringing up the connection.

```bash
nmcli con add type wifi ifname wlan0 mode ap con-name X6200-AP ssid X6200 autoconnect false
nmcli con modify X6200-AP wifi.band bg
nmcli con modify X6200-AP wifi.channel 3
nmcli con modify X6200-AP wifi-sec.key-mgmt wpa-psk
nmcli con modify X6200-AP wifi-sec.proto rsn
nmcli con modify X6200-AP wifi-sec.group ccmp
nmcli con modify X6200-AP wifi-sec.pairwise ccmp
nmcli con modify X6200-AP wifi-sec.psk "x6200wifipassword"
nmcli con modify X6200-AP ipv4.method shared ipv4.address 192.168.62.1/24
nmcli con modify X6200-AP ipv6.method disabled
```

```bash
nmcli con up X6200-AP
```
