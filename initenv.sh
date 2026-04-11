echo  'KERNEL=="ttyUSB*", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", MODE:="0777", GROUP:="dialout", SYMLINK+="tetra/motor"' >/etc/udev/rules.d/tetra_motor.rules
echo  'KERNEL=="ttyUSB*", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", MODE:="0777", GROUP:="dialout", SYMLINK+="tetra/motor"' >/etc/udev/rules.d/tetra_motor.rules
echo  'KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE:="0777", ATTRS{serial}=="f14c918decbb5947858e587ae34fe2ec", GROUP:="dialout",  SYMLINK+="tetra/lidar"' >/etc/udev/rules.d/tetra_lidar.rules

# echo  'KERNEL=="ttyUSB*", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6014", MODE:="0666", ATTRS{serial}=="0000:00:14.0", GROUP:="dialout",  SYMLINK+="tetra/servo"' >/etc/udev/rules.d/tetra_servo.rules

service udev reload
sleep 2
service udev restart


