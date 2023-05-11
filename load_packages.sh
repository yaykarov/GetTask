#!/usr/bin/env bash

# Install Chrome.
#wget -N https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -P ~/
#sudo dpkg -i --force-depends ~/google-chrome-stable_current_amd64.deb
#sudo apt-get -f install -y
#sudo dpkg -i --force-depends ~/google-chrome-stable_current_amd64.deb
sudo apt-get install chromium-browser

# Install ChromeDriver.
wget https://chromedriver.storage.googleapis.com/2.35/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/bin
rm chromedriver_linux64.zip

