import threading

# Lock global para serializar chamadas ao bluetoothctl.
# Compartilhado entre main.py (loop principal) e webapp/app.py (rotas de scan/pair).
bt_lock = threading.Lock()
