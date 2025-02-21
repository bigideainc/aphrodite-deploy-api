import paramiko

hostname = "24.83.13.62"
port = 15000  # or 14000, whichever works manually
username = "tang"
password = "Yogptcommune1"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(hostname=hostname, port=port, username=username, password=password)
    print("Connection successful!")
except Exception as e:
    print("Connection failed:", e)
finally:
    client.close()
