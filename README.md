# ShoprAPI
Follow these steps to setup the API on EC2 using Apache to serve requests.

- Create EC2 instance using Amazon Linux AMI then ssh into it
- Create project base directory
~~~~
sudo mkdir /var/www
~~~~
- Install Git, Apache/httpd, and WSGI
~~~~
sudo yum install git httpd mod_wsgi
~~~~
- Clone ShoprAPI
~~~~
cd /var/www && sudo git clone https://github.com/nalliso/ShoprAPI
~~~~
- Create project group
~~~~
sudo groupadd www
~~~~
- Add ec2-user to project group
~~~~
sudo usermod -aG www ec2-user
~~~~
- Set group of www directory to www
~~~~
sudo chgrp -R www /var/www
~~~~
- Install project requirements
~~~~
cd /var/www && sudo pip install -r requirements.txt
~~~~
- Start apache
~~~~
sudo service httpd start
~~~~

Everything should be good to go at this point and you can test locally by running the python script
~~~~
python api.py
~~~~
