import os
import subprocess
import uuid
import sys

import nest_asyncio
import uvicorn
from pyngrok import ngrok


try:
    from google.colab import drive

    colab_env = True
except ImportError:
    colab_env = False


EXTENSIONS = ["ms-python.python", "ms-toolsai.jupyter"]
CODESERVER_VERSION = "3.9.0"


class ColabCode:
    def __init__(
        self,
        port=10000,
        password=None,
        authtoken=None,
        mount_drive=False,
        code=True,
        lab=False,
        tunnel="ngrok"
    ):
        self.port = port
        self.password = password
        self.authtoken = authtoken
        self._mount = mount_drive
        self._code = code
        self._lab = lab
        self.tunnel = tunnel
        if tunnel == "localtunnel":
            self._install_localtunnel()
        self.connection = None
        try:
            if self._lab:
                self._start_server()
                self._run_lab()
            if self._code:
                self._install_code()
                self._install_extensions()
                self._start_server()
                self._run_code()
        except KeyboardInterrupt:
            if self.tunnel == "localtunnel" and self.connection:
                try:
                    self.connection.kill()
                except:
                    pass
            sys.exit(0)

    @staticmethod
    def _install_code():
        subprocess.run(
            ["bash", "-c", "curl -L https://code-server.dev/install.sh | sh"],
            stdout=subprocess.PIPE,
        )

    @staticmethod
    def _install_localtunnel():
        subprocess.run(["npm", "install", "-g", "localtunnel"], stdout=subprocess.PIPE)

    @staticmethod
    def _install_extensions():
        for ext in EXTENSIONS:
            subprocess.run(["code-server", "--install-extension", f"{ext}"])

    def _start_server(self):
        if self.tunnel == "ngrok":
            if self.authtoken:
                ngrok.set_auth_token(self.authtoken)
            active_tunnels = ngrok.get_tunnels()
            for tunnel in active_tunnels:
                public_url = tunnel.public_url
                ngrok.disconnect(public_url)
            url = ngrok.connect(addr=self.port, options={"bind_tls": True})
            if self._code:
                print(f"Code Server can be accessed on: {url}")
            else:
                print(f"Public URL: {url}")
        elif self.tunnel == "localtunnel":
            connection = subprocess.Popen(["lt", "--port", str(self.port)], stdout=subprocess.PIPE)
            for line in iter(connection.stdout.readline, ''):
                print(line.rstrip().decode())
                break
            self.connection = connection
        else:
            raise Exception(f"mode is invalid: {self.tunnel}")

    def _run_lab(self):
        token = str(uuid.uuid1())
        print(f"Jupyter lab token: {token}")
        base_cmd = "jupyter-lab --ip='localhost' --allow-root --ServerApp.allow_remote_access=True --no-browser"
        os.system(f"fuser -n tcp -k {self.port}")
        if self._mount and colab_env:
            drive.mount("/content/drive")
        if self.password:
            lab_cmd = f" --ServerApp.token='{token}' --ServerApp.password='{self.password}' --port {self.port}"
        else:
            lab_cmd = f" --ServerApp.token='{token}' --ServerApp.password='' --port {self.port}"
        lab_cmd = base_cmd + lab_cmd
        with subprocess.Popen(
            [lab_cmd],
            shell=True,
            stdout=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        ) as proc:
            for line in proc.stdout:
                print(line, end="")

    def _run_code(self):
        os.system(f"fuser -n tcp -k {self.port}")
        if self._mount and colab_env:
            drive.mount("/content/drive")
        if self.password:
            code_cmd = f"PASSWORD={self.password} code-server --port {self.port} --disable-telemetry"
        else:
            code_cmd = f"code-server --port {self.port} --auth none --disable-telemetry"
        with subprocess.Popen(
            [code_cmd],
            shell=True,
            stdout=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        ) as proc:
            for line in proc.stdout:
                print(line, end="")

    def run_app(self, app, workers=1):
        self._start_server()
        nest_asyncio.apply()
        uvicorn.run(app, host="127.0.0.1", port=self.port, workers=workers)
