install:
	cp X2DDaemon.py /usr/bin
	chmod 755 /usr/bin/X2DDaemon.py
	cp x2ddaemon.service /etc/systemd/system/
	systemctl daemon-reload
	mkdir -p /var/log/X2Ddaemon
	chmod 755 /var/log/X2Ddaemon

.PHONY: install

