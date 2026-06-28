import docker
client = docker.from_env()
try:
    img = client.images.get('ctf-challenge2:latest')
    print("ctf-challenge2:", img.attrs.get('Config', {}).get('ExposedPorts'))
except Exception as e:
    print(e)
