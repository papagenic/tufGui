# tufGui : an GUI interface for flow meter TUF 2000
To install the code
git clone the project. 
rename the project forlder to TUF2000
cd tuf2000
create python environment TUFvenv
python3 -m venv TUFvenv
activate the environment: source TUFvenv/bin/activate
install dependancies
pip install -r requirements.txt
create data folder
sudo mkdir /var/log/TUF2000
sudo chmod 777 /var/log/TUF2000


install systemd service
edit systemd/tufgui.service and change setting, including the user under which the service will run 
add this user to the dialout group so that it can access the serial port
sudo usermod -a -G dialout serviceUser
sudo cp systemd/tufgui.service  /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable tufgui.service
sudo systemctl start tufgui.service
