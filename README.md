## TTS install

```bash
pip3 install gtts playsound
pip3 install pydub
```

## Port Setup

```bash
cd ~/ros2_ws/src/tetra
sudo chmod 777 ./initenv.sh
sudo ./initenv.sh
```

## Robot Bringup

```bash
ros2 launch tetra tetra_configuration.launch.py
```

## SLAM

```bash
ros2 launch tetra_cartographer cartographer_slam.launch.py
```

## NAVI

```bash
ros2 launch tetra_nav2 nav2.launch.py
```

### TTS server launch

```bash
ros2 launch bmkbot_io bmkbot_io.launch.py
```

### FlexBE launch

```bash
ros2 launch flexbe_app flexbe_full.launch.py  
```

### GUI launch

```jsx
ros2 launch bmkbot_gui bmkbot_gui.launch.py
```