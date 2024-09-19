# Wifi
Issues connecting to Wifi through UI can be resolved by using CLI.

**Note:** Ensure Wifi is switched on from the radio UI first

List access points
`nmcli device wifi`

Connect to an access point
`nmcli device wifi connect '<AP NAME>' password '<PASSWORD>'`
