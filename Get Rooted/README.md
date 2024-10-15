# Root Account
## Firmware Version 1.0.1

User: root

Pass: 123

### /etc/passwd
```
root:x:0:0:root:/root:/bin/sh
daemon:x:1:1:daemon:/usr/sbin:/bin/false
bin:x:2:2:bin:/bin:/bin/false
sys:x:3:3:sys:/dev:/bin/false
sync:x:4:100:sync:/bin:/bin/sync
mail:x:8:8:mail:/var/spool/mail:/bin/false
www-data:x:33:33:www-data:/var/www:/bin/false
operator:x:37:37:Operator:/var:/bin/false
nobody:x:65534:65534:nobody:/home:/bin/false
dbus:x:1000:1000:DBus messagebus user:/var/run/dbus:/bin/false
sshd:x:1001:1004:SSH drop priv user:/var/empty:/bin/false
pulse:x:1002:1005::/var/run/pulse:/bin/false
ftp:x:1003:1006:Anonymous FTP User:/home/ftp:/bin/false
```

### /etc/shadow
```
root:$5$n10aE5IfY4OTYphj$Vfd5tWACnq/p66OjwsG0eUKmnzGyCxeZnuHb2v3EvsA:::::::
daemon:*:::::::
bin:*:::::::
sys:*:::::::
sync:*:::::::
mail:*:::::::
www-data:*:::::::
operator:*:::::::
nobody:*:::::::
dbus:*:::::::
sshd:*:::::::
pulse:*:::::::
ftp:*:::::::
```

### Crack Hash
```bash
┌──(kali㉿kali)-[~/Desktop]
└─$ john shadow --show
root:123:::::::

1 password hash cracked, 0 left
```

## Firmware Version 1.0.3

User: root

Pass: 123

### /etc/passwd
```
root:x:0:0:root:/root:/bin/sh
daemon:x:1:1:daemon:/usr/sbin:/bin/false
bin:x:2:2:bin:/bin:/bin/false
sys:x:3:3:sys:/dev:/bin/false
sync:x:4:100:sync:/bin:/bin/sync
mail:x:8:8:mail:/var/spool/mail:/bin/false
www-data:x:33:33:www-data:/var/www:/bin/false
operator:x:37:37:Operator:/var:/bin/false
nobody:x:65534:65534:nobody:/home:/bin/false
dbus:x:1000:1000:DBus messagebus user:/var/run/dbus:/bin/false
sshd:x:1001:1004:SSH drop priv user:/var/empty:/bin/false
pulse:x:1002:1005::/var/run/pulse:/bin/false
ftp:x:1003:1006:Anonymous FTP User:/home/ftp:/bin/false
```

### /etc/shadow
```
root:$5$k.8Q8O5hsBCH59x$L7p2vm8bzZobYCi9yYJCY1NJ01cpIrqFwvgbOtWEnLD:::::::
daemon:*:::::::
bin:*:::::::
sys:*:::::::
sync:*:::::::
mail:*:::::::
www-data:*:::::::
operator:*:::::::
nobody:*:::::::
dbus:*:::::::
sshd:*:::::::
pulse:*:::::::
ftp:*:::::::
```

### Crack Hash
```bash
┌──(kali㉿kali)-[~/Desktop]
└─$ john shadow --show
root:123:::::::

1 password hash cracked, 0 left
```
