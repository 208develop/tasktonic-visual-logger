#!/bin/bash

# Update package list
sudo apt-get update

# Install all required graphical and XCB libraries for PySide6
sudo apt-get install -y libgl1-mesa-glx libxkbcommon-x11-0 libxcb-cursor0 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
    libxcb-xinerama0 libxcb-xkb1 libx11-xcb1 libxcb-shape0 libxcb-randr0 \
    libxcb-util1 libegl1

# Install PySide6 and TaskTonic
pip install PySide6 TaskTonic

echo "Setup finished successfully!"
